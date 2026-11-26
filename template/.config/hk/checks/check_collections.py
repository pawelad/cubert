#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Fail when the installed Ansible collections differ from requirements.yml.

`ansible:install` installs into `<ansible dir>/collections`. The set must match the
pins exactly, and with no requirements.yml it must be empty. A collection that the
project keeps in git has no MANIFEST.json, so the check skips it.

`--staged <dir>` checks a fresh install before ansible:install swaps it in. There, a
difference is a pin to fix, such as a dependency that requirements.yml does not pin.

Usage: check_collections.py [--quiet] [--staged <dir>] <ansible dir>
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

USAGE = __doc__.strip().splitlines()[-1]
FIX = "Fix: mise run ansible:install"
STAGED_FIX = (
    "Fix: pin each collection that Galaxy installed in requirements.yml, dependencies"
    " included, with the version shown."
)
# Exit 1 means the set differs, which ansible:install fixes. Exit 2 means it cannot.
DIFFERS, BROKEN = 1, 2
# ansible-core ships PyYAML, so this script needs no dependency of its own.
LOAD_YAML = (
    "import json, sys, yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1]))))"
)
EXACT = re.compile(r"(==)?(\d+\.\d+\.\d+([-+][0-9A-Za-z.+-]*)?)")
NAME = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+")


def fail(message: str) -> NoReturn:
    """Exit with BROKEN: a download cannot fix the message's cause."""
    print(message, file=sys.stderr)
    raise SystemExit(BROKEN)


def ansible_python() -> str:
    """Return the interpreter that runs ansible-core, from `ansible --version`."""
    try:
        result = subprocess.run(
            ["ansible", "--version"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        fail("ansible is missing. Fix: mise run setup")
    if result.returncode != 0:
        fail(f"`ansible --version` failed:\n{result.stderr}")
    found = re.search(
        r"^\s*python version = .*\((/[^)]+)\)$", result.stdout, re.MULTILINE
    )
    if not found:
        fail("`ansible --version` named no Python interpreter.")
    return found.group(1)


def load_yaml(path: Path) -> object:
    """Parse the YAML file at `path` with ansible-core's Python."""
    result = subprocess.run(  # noqa: S603
        [ansible_python(), "-c", LOAD_YAML, str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        fail(f"{path}: cannot parse it as YAML:\n{result.stderr}")
    return json.loads(result.stdout)


def pinned(requirements: Path, data: object) -> dict[str, str]:
    """Return {name: version}. Each collection needs an exact version, such as 1.2.3."""
    if data is None:
        return {}
    entries = data.get("collections") if isinstance(data, dict) else None
    if not isinstance(data, dict) or not isinstance(entries or [], list):
        fail(f"{requirements}: needs a `collections:` list, as Galaxy reads it.")
    pins: dict[str, str] = {}
    for entry in entries or []:
        name = entry.get("name") if isinstance(entry, dict) else entry
        if not isinstance(name, str) or not NAME.fullmatch(name):
            fail(f"{requirements}: {name!r} is not a collection name: namespace.name.")
        version = str(entry.get("version", "")) if isinstance(entry, dict) else ""
        match = EXACT.fullmatch(version)
        if not match:
            fail(
                f"{requirements}: {name} needs an exact version, such as"
                f' version: "1.2.3", not {version!r}.'
            )
        pins[name] = match.group(2)
    return pins


def installed(collections: Path) -> dict[str, str]:
    """Return {name: version} from each installed collection's MANIFEST.json."""
    found: dict[str, str] = {}
    for manifest in sorted(collections.glob("ansible_collections/*/*/MANIFEST.json")):
        info = json.loads(manifest.read_text())["collection_info"]
        found[f"{info['namespace']}.{info['name']}"] = info["version"]
    return found


def problems(pins: dict[str, str], found: dict[str, str]) -> list[str]:
    """Return one line per collection that is missing, drifted or not pinned."""
    out = []
    for name, version in sorted(pins.items()):
        if name not in found:
            out.append(f"{name}: not installed (pinned {version})")
        elif found[name] != version:
            out.append(f"{name}: {found[name]} installed, pinned {version}")
    out += [
        f"{name}: {found[name]} installed, not in requirements.yml"
        for name in sorted(found.keys() - pins.keys())
    ]
    return out


def parse(argv: list[str]) -> tuple[bool, Path | None, Path]:
    """Return (quiet, staged, ansible dir), or exit BROKEN with the usage line."""
    quiet = "--quiet" in argv
    args = [a for a in argv if a != "--quiet"]
    staged = None
    if "--staged" in args:
        at = args.index("--staged")
        if at + 1 >= len(args):
            fail(USAGE)
        staged = Path(args.pop(at + 1))
        args.pop(at)
    if len(args) != 1:
        fail(USAGE)
    return quiet, staged, Path(args[0])


def main(argv: list[str]) -> int:
    """Return 0 when the installed set matches, DIFFERS or BROKEN otherwise."""
    quiet, staged, base = parse(argv)
    requirements = base / "requirements.yml"
    pins = (
        pinned(requirements, load_yaml(requirements)) if requirements.is_file() else {}
    )
    collections = staged or base / "collections"
    found = problems(pins, installed(collections))
    if found and not quiet:
        print(
            f"The collections in {collections} differ from {requirements}:",
            file=sys.stderr,
        )
        for line in found:
            print(f"  {line}", file=sys.stderr)
        print(STAGED_FIX if staged else FIX, file=sys.stderr)
    if not found:
        return 0
    return BROKEN if staged else DIFFERS


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
