#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""Fail when `mise.toml` lacks a tool that the shared hk steps and tasks call.

A template update can add a tool to `.config/mise/required-tools`, but it cannot add
the tool to the project-owned `mise.toml`.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

REQUIRED = Path(".config/mise/required-tools")
CONFIG = Path("mise.toml")


def missing(required: str, config: str) -> list[str]:
    """Return the tools in the `required` list that the `config` TOML lacks."""
    tools = tomllib.loads(config).get("tools", {})
    names = [line.strip() for line in required.splitlines()]
    return [
        name
        for name in names
        if name and not name.startswith("#") and name not in tools
    ]


def main(args: list[str]) -> int:
    """Print each required tool that `mise.toml` lacks. `--names` prints only names."""
    tools = missing(REQUIRED.read_text(), CONFIG.read_text())
    if args == ["--names"]:
        print("\n".join(tools))
        return 0
    for tool in tools:
        print(f"{CONFIG}: {tool} is missing, and the shared steps need it.")
    if tools:
        print("Fix: mise run setup")
    return 1 if tools else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
