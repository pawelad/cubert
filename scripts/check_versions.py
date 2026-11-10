#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""Fail when the template ships a tool version that cubert would have to keep current.

The template seeds `latest` (or `lts`), and the project's `mise run setup` pins it.
The one version left is the hk package, which must match cubert's own hk tool.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

TEMPLATE_TOOLS = Path("template/mise.toml.jinja")
HK_CONFIGS = (Path("template/.config/hk/base.pkl"), Path("template/.config/hk/cubert.pkl.jinja"))
UNPINNED = {"latest", "lts"}

TOOL_LINE = re.compile(r'^"?(?P<name>[^"=\s]+)"? = "(?P<version>[^"]+)"$')
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


def failures(root: Path) -> list[str]:
    own = tomllib.loads((root / "mise.toml").read_text())["tools"]
    found: list[str] = []

    for name, version in template_tools((root / TEMPLATE_TOOLS).read_text()).items():
        if version not in UNPINNED:
            found.append(f"{TEMPLATE_TOOLS}: seed {name} = \"latest\", not {version!r}")

    for path in HK_CONFIGS:
        for match in HK_PACKAGE.finditer((root / path).read_text()):
            if not match["tag"] == match["version"] == own["hk"]:
                found.append(f"{path}: hk package {match['version']!r}, mise.toml has {own['hk']!r}")

    return found


def main() -> int:
    found = failures(Path())
    for failure in found:
        print(failure)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
