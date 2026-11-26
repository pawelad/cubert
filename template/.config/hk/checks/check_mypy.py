#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Run mypy on plain files in the project env, and on each PEP 723 script in its own.

A script's env holds only its inline dependencies, so an import that the inline block
misses fails here, and not for the people who run the script. A plain file that matches
ruff's `per-file-target-version` is checked for that Python, as ruff formats it. Plain
files that share a module name go to separate mypy calls.
"""

from __future__ import annotations

import fnmatch
import functools
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

# The reference regex from PEP 723.
BLOCK = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)

# The oldest Python that `requires-python` allows, such as 3.11 in ">=3.11, <4".
MINIMUM = re.compile(r">=\s*(\d+\.\d+)")

# ruff's config files in its order of precedence, and the table that holds its settings.
RUFF_CONFIGS = (
    (".ruff.toml", ()),
    ("ruff.toml", ()),
    ("pyproject.toml", ("tool", "ruff")),
)

# This script runs in its own uv env, and child uv commands must not inherit it.
BASE_ENV = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}


def script_metadata(path: Path) -> dict[str, object] | None:
    """Return the PEP 723 `script` block of a Python file, or None when it has none."""
    if path.suffix != ".py":
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for match in BLOCK.finditer(text):
        if match["type"] == "script":
            lines = match["content"].splitlines(keepends=True)
            body = "".join(
                line[2:] if line.startswith("# ") else line[1:] for line in lines
            )
            try:
                return tomllib.loads(body)
            except tomllib.TOMLDecodeError:
                # uv reports the bad block, so the script still goes to its own env.
                return {}
    return None


def minimum_python(metadata: dict[str, object]) -> str | None:
    """Return the oldest Python that the script allows, such as "3.11"."""
    match = MINIMUM.search(str(metadata.get("requires-python", "")))
    return match[1] if match else None


@functools.cache
def mypy_minimum() -> str | None:
    """Return the oldest `--python-version` that the project's mypy accepts."""
    code = "from mypy.defaults import PYTHON3_VERSION_MIN as v; print(*v, sep='.')"
    found = subprocess.run(  # noqa: S603
        ["uv", "run", "python", "-c", code],  # noqa: S607
        capture_output=True,
        text=True,
        env=BASE_ENV,
        check=False,
    )
    if found.returncode != 0:
        return None
    return found.stdout.strip() or None


def target_python(metadata: dict[str, object]) -> str | None:
    """Return the script's oldest Python, raised to mypy's floor (mypy 2.x: 3.10)."""
    return _raise_to_floor(minimum_python(metadata))


def _raise_to_floor(version: str | None) -> str | None:
    floor = mypy_minimum() if version else None
    if version and floor and _numbers(version) < _numbers(floor):
        return floor
    return version


@functools.cache
def ruff_targets() -> dict[str, str]:
    """Return the root ruff config's `per-file-target-version`, as globs to versions."""
    for name, table in RUFF_CONFIGS:
        try:
            config: object = tomllib.loads(Path(name).read_text(encoding="utf-8"))
        except OSError:
            continue
        except tomllib.TOMLDecodeError:
            return {}
        for key in table:
            config = config.get(key) if isinstance(config, dict) else None
        # ruff skips a pyproject.toml without a ruff table, and stops at any other.
        if config is None and table:
            continue
        targets = (
            config.get("per-file-target-version") if isinstance(config, dict) else None
        )
        if not isinstance(targets, dict):
            return {}
        return {
            glob: f"{version[2]}.{version[3:]}"
            for glob, version in targets.items()
            if isinstance(version, str) and re.fullmatch(r"py3\d+", version)
        }
    return {}


def _glob_matches(text: str, pattern: str) -> bool:
    """Match a ruff glob, where `*` crosses `/` and `**/` can match zero dirs."""
    if fnmatch.fnmatchcase(text, pattern):
        return True
    if pattern.startswith("**/") and _glob_matches(text, pattern[3:]):
        return True
    if "/**/" in pattern:
        before, _, after = pattern.partition("/**/")
        return _glob_matches(text, f"{before}/{after}") or _glob_matches(
            text, f"{before}/*/{after}"
        )
    return False


def plain_python(path: Path) -> str | None:
    """Return the Python that ruff targets for a plain file, or None for the default."""
    # ruff matches a glob against the path or the file name, and `*` crosses `/`.
    relative = Path(os.path.relpath(path.resolve(), Path.cwd().resolve())).as_posix()
    for glob, version in ruff_targets().items():
        pattern = glob.removeprefix("./")
        if _glob_matches(relative, pattern) or _glob_matches(path.name, pattern):
            return _raise_to_floor(version)
    return None


def _numbers(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def script_python(path: Path) -> str | None:
    """Sync the script's env and return its interpreter, or None when uv fails."""
    command = ["uv", "sync", "--quiet", "--script", str(path)]
    # A check must not rewrite a lock. An exported `UV_LOCKED` fails an unlocked script.
    locked = path.with_name(f"{path.name}.lock").exists()
    env = {k: v for k, v in BASE_ENV.items() if k not in {"UV_LOCKED", "UV_FROZEN"}}
    sync = subprocess.run(  # noqa: S603
        [*command, "--locked"] if locked else command, env=env, check=False
    )
    if sync.returncode != 0:
        fix = f" Run `uv lock --script {path}`." if locked else ""
        print(f"{path}: `uv sync --script` failed, see above.{fix}", file=sys.stderr)
        return None
    found = subprocess.run(  # noqa: S603
        ["uv", "python", "find", "--script", str(path)],  # noqa: S607
        capture_output=True,
        text=True,
        env=BASE_ENV,
        check=False,
    )
    if found.returncode != 0:
        print(f"{path}: {found.stderr.strip()}", file=sys.stderr)
        return None
    return found.stdout.strip()


def module_name(path: Path) -> str:
    """Return the module name that mypy gives a file, such as "pkg.mod" or "mod"."""
    # As mypy's `find_sources`: no symlink resolution, and no climb past a folder that
    # is not an identifier, after a stub-only `-stubs` suffix.
    parts = [] if path.stem == "__init__" else [path.stem]
    folder = Path(os.path.abspath(path)).parent  # noqa: PTH100
    while any((folder / f"__init__{suffix}").is_file() for suffix in (".py", ".pyi")):
        name = folder.name.removesuffix("-stubs")
        if not name.isidentifier():
            break
        parts.insert(0, name)
        folder = folder.parent
    return ".".join(parts)


def without_clashes(paths: list[str]) -> list[list[str]]:
    """Split paths into the fewest calls in which no two files share a module name."""
    # One mypy call rejects two files with one module name: "Duplicate module named".
    calls: list[list[str]] = []
    names: list[set[str]] = []
    for path in paths:
        name = module_name(Path(path))
        index = next((i for i, seen in enumerate(names) if name not in seen), None)
        if index is None:
            calls.append([])
            names.append(set())
            index = -1
        calls[index].append(path)
        names[index].add(name)
    return calls


def mypy(*args: str) -> int:
    """Run the project's mypy, so every file shares its `[tool.mypy]` settings."""
    command = ["uv", "run", "mypy", *args]
    return subprocess.run(command, env=BASE_ENV, check=False).returncode  # noqa: S603


def main(argv: list[str]) -> int:
    """Check `argv` files and return 1 when any mypy run fails."""
    files = [Path(arg) for arg in argv]
    scripts = {path: script_metadata(path) for path in files}
    plain: dict[str | None, list[str]] = {}
    for path, metadata in scripts.items():
        if metadata is None:
            plain.setdefault(plain_python(path), []).append(str(path))
    failed = False
    for version, paths in plain.items():
        target = ["--python-version", version] if version else []
        for call in without_clashes(paths):
            if mypy(*target, *call) != 0:
                failed = True
    for path, metadata in scripts.items():
        if metadata is None:
            continue
        python = script_python(path)
        if python is None:
            failed = True
            continue
        # Users can run the script on its oldest Python, so mypy parses for that one.
        version = target_python(metadata)
        target = ["--python-version", version] if version else []
        if mypy("--python-executable", python, *target, str(path)) != 0:
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
