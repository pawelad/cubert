#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""Fail on unpinned tool versions in `mise.toml` and unpinned GitHub Actions.

A mise tool must name a version, not `latest`. A remote action must use a full
version tag (`@v1.2.3`) or a commit SHA. Hadolint and dclint check Docker images.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

USES = re.compile(r"^\s*(?:-\s+)?uses:\s*[\"']?([^\"'\s#]+)")
PINNED_REF = re.compile(r"^(v?\d+\.\d+\.\d+([.-][0-9A-Za-z.-]+)?|[0-9a-f]{40})$")


def _mise_failures(path: Path) -> list[str]:
    tools = tomllib.loads(path.read_text()).get("tools", {})
    failures = []
    for name, spec in tools.items():
        versions = spec if isinstance(spec, list) else [spec]
        for version in versions:
            value = version.get("version") if isinstance(version, dict) else version
            if not isinstance(value, str) or value in {"latest", ""}:
                failures.append(f"{path}: tool {name!r} has no pinned version")
    return failures


def _actions_failures(path: Path) -> list[str]:
    failures = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        match = USES.match(line)
        if not match:
            continue
        action = match.group(1)
        if action.startswith(("./", "docker://")):
            continue
        _, _, ref = action.partition("@")
        if not PINNED_REF.match(ref):
            failures.append(f"{path}:{number}: pin {action!r} to @vX.Y.Z or a commit SHA")
    return failures


def main(paths: list[str]) -> int:
    failures: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.name == "mise.toml":
            failures += _mise_failures(path)
        elif path.suffix in {".yml", ".yaml"}:
            failures += _actions_failures(path)
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
