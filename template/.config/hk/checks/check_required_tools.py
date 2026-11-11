#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Fail when `mise.toml` lacks a tool, or has one too old, for the shared hk steps.

A template update can add a tool or raise its minimum in `.config/mise/required-tools`
(`hk>=2.11.1`), but it cannot change the project-owned `mise.toml`.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REQUIRED = Path(".config/mise/required-tools")
CONFIG = Path("mise.toml")


# `node@lts` adds the tool from a channel. A scoped npm name keeps its own `@`.
LINE = re.compile(r"(?P<name>.+?)(?:@(?P<channel>[a-z]+))?(?:>=(?P<minimum>.+))?")


def _requirements(required: str) -> list[tuple[str, str | None, str | None]]:
    """Return (name, minimum version, channel) for each line of the required list."""
    found = []
    for raw in required.splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and (match := LINE.fullmatch(line)):
            found.append((match["name"], match["minimum"], match["channel"]))
    return found


def _numbers(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:3])


def _configured_version(spec: object) -> str | None:
    """Return the version of a tool entry, or None for a list or an alias."""
    value = spec.get("version") if isinstance(spec, dict) else spec
    return value if isinstance(value, str) and re.match(r"v?\d", value) else None


def missing(required: str, config: str) -> list[str]:
    """Return the tools in the `required` list that the `config` TOML lacks."""
    tools = tomllib.loads(config).get("tools", {})
    return [name for name, _, _ in _requirements(required) if name not in tools]


def outdated(required: str, config: str) -> list[tuple[str, str, str]]:
    """Return (name, minimum, configured) for each tool below its minimum version."""
    tools = tomllib.loads(config).get("tools", {})
    found = []
    for name, minimum, _ in _requirements(required):
        configured = _configured_version(tools.get(name))
        if minimum and configured and _numbers(configured) < _numbers(minimum):
            found.append((name, minimum, configured))
    return found


def main(args: list[str]) -> int:
    """Print each tool that `mise.toml` lacks or has too old. `--names` prints fixes."""
    required, config = REQUIRED.read_text(), CONFIG.read_text()
    tools = missing(required, config)
    old = outdated(required, config)
    if args == ["--names"]:
        channels = {name: channel for name, _, channel in _requirements(required)}
        added = [
            f"{tool}@{channels[tool]}" if channels[tool] else tool for tool in tools
        ]
        print("\n".join([*added, *(f"{name}@{minimum}" for name, minimum, _ in old)]))
        return 0
    for tool in tools:
        print(f"{CONFIG}: {tool} is missing, and the shared steps need it.")
    for name, minimum, configured in old:
        print(f"{CONFIG}: {name} {configured} is below {minimum}, the minimum.")
    if tools or old:
        print("Fix: mise run setup")
    return 1 if tools or old else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
