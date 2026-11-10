#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""Fail when a version that cubert pins in several places differs between them.

cubert's own `mise.toml` is the reference. The template seeds the same tool
versions, pins the hk package to the hk tool, and pins Copier in its tasks.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

TEMPLATE_TOOLS = Path("template/mise.toml.jinja")
HK_CONFIGS = (Path("template/.config/hk/base.pkl"), Path("template/.config/hk/cubert.pkl.jinja"))
COPIER_TASKS = (
    Path("template/.config/mise/tasks/template/update"),
    Path("template/.config/mise/tasks/template/check"),
)

TOOL_LINE = re.compile(r'^"?(?P<name>[^"=\s]+)"? = "(?P<version>[^"]+)"$')
HK_PACKAGE = re.compile(r"hk/releases/download/v(?P<tag>[^/]+)/hk@(?P<version>[^#]+)#")
COPIER_PIN = re.compile(r"copier@(?P<version>[0-9][^\s)]*)")


def template_tools(text: str) -> dict[str, str]:
    """Return the tool pins that the template seeds, across every feature block."""
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


def failures(root: Path) -> list[str]:
    own = tomllib.loads((root / "mise.toml").read_text())["tools"]
    found: list[str] = []

    for name, version in template_tools((root / TEMPLATE_TOOLS).read_text()).items():
        if name in own and own[name] != version:
            found.append(f"{TEMPLATE_TOOLS}: {name} = {version!r}, mise.toml has {own[name]!r}")

    for path in HK_CONFIGS:
        for match in HK_PACKAGE.finditer((root / path).read_text()):
            if not match["tag"] == match["version"] == own["hk"]:
                found.append(f"{path}: hk package {match['version']!r}, mise.toml has {own['hk']!r}")

    for path in COPIER_TASKS:
        pins = COPIER_PIN.findall((root / path).read_text())
        if not pins:
            found.append(f"{path}: no copier@<version> pin found")
        found += [
            f"{path}: copier@{pin}, mise.toml has {own['pipx:copier']!r}"
            for pin in pins
            if pin != own["pipx:copier"]
        ]
    return found


def main() -> int:
    found = failures(Path())
    for failure in found:
        print(failure)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
