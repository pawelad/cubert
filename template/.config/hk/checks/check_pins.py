#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""Fail on unpinned tool versions in `mise.toml`.

A mise tool must name a version, not `latest` or `lts`. zizmor checks the GitHub
Actions pins, and hadolint and dclint check the Docker images.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path


def _mise_failures(path: Path) -> list[str]:
    tools = tomllib.loads(path.read_text()).get("tools", {})
    failures = []
    for name, spec in tools.items():
        versions = spec if isinstance(spec, list) else [spec]
        for version in versions:
            value = version.get("version") if isinstance(version, dict) else version
            if not isinstance(value, str) or value in {"latest", "lts", ""}:
                failures.append(f"{path}: tool {name!r} has no pinned version")
    return failures


def main(paths: list[str]) -> int:
    """Print each unpinned tool in the `mise.toml` files in `paths`."""
    failures: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.name == "mise.toml":
            failures += _mise_failures(path)
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
