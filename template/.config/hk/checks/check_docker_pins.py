#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Fail when a Dockerfile `ARG <TOOL>_VERSION` default differs from the mise pin.

Dependabot cannot bump a `FROM` tag that reads an ARG, so `mise.toml` is the one
source, and `mise run upgrade` passes `--fix` to copy each pin into the Dockerfiles.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

# Instructions are case-insensitive, and ARG names are not.
ARG = re.compile(
    r"""^(?P<head>\s*(?i:arg)\s+(?P<name>[A-Z0-9_]+)_VERSION=)
    (?P<quote>["']?)(?P<value>[^"'\s$]+)(?P=quote)(?P<tail>\s*)$""",
    re.VERBOSE,
)


def mise_pins(path: Path) -> dict[str, tuple[str, str]]:
    """Map the ARG prefix of each plain tool in `path` to its name and version."""
    pins: dict[str, tuple[str, str]] = {}
    for name, spec in tomllib.loads(path.read_text()).get("tools", {}).items():
        # A backend key such as `npm:dclint` has no conventional ARG name.
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            continue
        # mise activates the first version of a list.
        first = spec[0] if isinstance(spec, list) and spec else spec
        value = first.get("version") if isinstance(first, dict) else first
        # Before setup pins it, a `latest` or `lts` request names no image tag.
        if isinstance(value, str) and re.match(r"v?\d", value):
            pins[name.upper().replace("-", "_")] = (name, value)
    return pins


def dockerfiles() -> list[Path]:
    """Return the Dockerfiles that git tracks or would track, without templates."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    paths = {Path(line) for line in listed}
    return sorted(
        path
        for path in paths
        if (path.name.startswith("Dockerfile") or path.suffix == ".Dockerfile")
        and path.suffix not in {".dockerignore", ".j2", ".jinja"}
        and path.is_file()
    )


def drift(path: Path, pins: dict[str, tuple[str, str]], *, fix: bool) -> list[str]:
    """Return each ARG default in `path` that differs from its mise pin."""
    lines = path.read_text().splitlines(keepends=True)
    failures: list[str] = []
    for number, line in enumerate(lines, start=1):
        match = ARG.match(line.rstrip("\n"))
        if not match or match["name"] not in pins:
            continue
        actual = match["value"]
        tool, pin = pins[match["name"]]
        if actual.removeprefix("v") == pin.removeprefix("v"):
            continue
        # Image tags differ on the `v` prefix, so the fix keeps the ARG's style.
        expected = "v" * actual.startswith("v") + pin.removeprefix("v")
        arg = f"{match['name']}_VERSION"
        fixed = f"{match['head']}{match['quote']}{expected}{match['quote']}"
        if fix:
            lines[number - 1] = fixed + match["tail"] + "\n" * line.endswith("\n")
            failures.append(f"{path}:{number}: ARG {arg}={actual} -> {expected}")
            continue
        failures.append(
            f"{path}:{number}: ARG {arg}={actual} does not match mise.toml"
            f" {tool} ({pin}). Fix: {fixed.strip()}"
        )
    if fix and failures:
        path.write_text("".join(lines))
    return failures


def main(argv: list[str]) -> int:
    """Print each drifted ARG default, or with `--fix`, rewrite it to the mise pin."""
    fix = "--fix" in argv
    config = Path("mise.toml")
    pins = mise_pins(config) if config.is_file() else {}
    failures = [line for path in dockerfiles() for line in drift(path, pins, fix=fix)]
    for failure in failures:
        print(failure)
    return 0 if fix else 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
