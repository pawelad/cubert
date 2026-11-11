#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""Fail when the template ships a tool version that cubert would have to keep current.

The template seeds `latest` (or `lts`), and the project's `mise run setup` pins it.
`check:repo` requires each seeded tool. The hk package must match cubert's own hk tool.
Dependabot skips `.jinja` workflows, so their actions must match the versions in the
workflows that it bumps.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

TEMPLATE_TOOLS = Path("template/mise.toml.jinja")
REQUIRED_TOOLS = Path("template/.config/mise/required-tools.jinja")
HK_CONFIGS = (
    Path("template/.config/hk/base.pkl"),
    Path("template/.config/hk/cubert.pkl.jinja"),
    Path("hk.pkl"),
)
UNPINNED = {"latest", "lts"}

TOOL_LINE = re.compile(r'^"?(?P<name>[^"=\s]+)"? = "(?P<version>[^"]+)"$')
USES = re.compile(r'uses:\s*"?(?P<action>[^"@\s.][^"@\s]*)@(?P<ref>[^"\s#]+)')
HK_PACKAGE = re.compile(r"hk/releases/download/v(?P<tag>[^/]+)/hk@(?P<version>[^#]+)#")


def template_tools(text: str) -> dict[str, str]:
    """Return the tool versions that the template seeds, across every feature block."""
    tools: dict[str, str] = {}
    in_tools = False
    for line in text.splitlines():
        if line.startswith("[") and not line.startswith("[%"):
            in_tools = line == "[tools]"
            continue
        match = TOOL_LINE.match(line)
        if in_tools and match:
            tools[match["name"]] = match["version"]
    return tools


def required_tools(text: str) -> set[str]:
    """Return the tools that `check:repo` requires, across every feature block."""
    return {
        line for line in text.splitlines() if line and not line.startswith(("[%", "#"))
    }


def action_refs(text: str) -> dict[str, str]:
    """Return the version of each remote action that a workflow uses."""
    return {match["action"]: match["ref"] for match in USES.finditer(text)}


def tool_failures(root: Path) -> list[str]:
    """Return each seeded tool with a version, and any drift from the required list."""
    found: list[str] = []
    seeded = template_tools((root / TEMPLATE_TOOLS).read_text())
    for name, version in seeded.items():
        if version not in UNPINNED:
            found.append(f'{TEMPLATE_TOOLS}: seed {name} = "latest", not {version!r}')

    required = required_tools((root / REQUIRED_TOOLS).read_text())
    if required != set(seeded):
        found.append(
            f"{REQUIRED_TOOLS}: required tools differ from {TEMPLATE_TOOLS}:"
            f" {sorted(required ^ set(seeded))}"
        )
    return found


def hk_failures(root: Path) -> list[str]:
    """Return each hk package import whose version differs from cubert's hk tool."""
    own = tomllib.loads((root / "mise.toml").read_text())["tools"]["hk"]
    return [
        f"{path}: hk package {match['version']!r}, mise.toml has {own!r}"
        for path in HK_CONFIGS
        for match in HK_PACKAGE.finditer((root / path).read_text())
        if not match["tag"] == match["version"] == own
    ]


def action_failures(root: Path) -> list[str]:
    """Return each action in a `.jinja` workflow that Dependabot bumped elsewhere."""
    found: list[str] = []
    plain = [*root.glob(".github/**/*.yml"), *root.glob("template/.github/**/*.yml")]
    bumped: dict[str, str] = {}
    for path in sorted(plain):
        bumped |= action_refs(path.read_text())
    for path in sorted(root.glob("template/.github/**/*.yml.jinja")):
        for action, ref in action_refs(path.read_text()).items():
            if action in bumped and bumped[action] != ref:
                found.append(
                    f"{path.relative_to(root)}: {action}@{ref},"
                    f" other workflows use @{bumped[action]}"
                )
    return found


def failures(root: Path) -> list[str]:
    """Return every failure in the repository at `root`."""
    return tool_failures(root) + hk_failures(root) + action_failures(root)


def main() -> int:
    """Print the failures in the current directory."""
    found = failures(Path())
    for failure in found:
        print(failure)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
