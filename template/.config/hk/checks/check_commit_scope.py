#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Fail on a changelog commit whose scope is not a `cliff.toml` area.

A `feat`, `fix`, `perf` or breaking commit needs an area scope or a tooling scope.
With no `cliff.toml`, or an empty `areas` list, every scope passes. The PR title job
runs this with the runner's `python3`, so it stays stdlib-only.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

CHANGELOG_TYPES = frozenset({"feat", "fix", "perf"})
SUBJECT_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?(?P<breaking>!)?: ")
BREAKING_FOOTER_RE = re.compile(r"^BREAKING[ -]CHANGE: ", re.MULTILINE)
AREAS_RE = re.compile(r"\{%\s*set areas = \[(?P<items>[^\]]*)\]\s*%\}")
AREA_RE = re.compile(r'"(?P<scope>[a-z0-9-]+)(?::(?P<heading>[^":][^"]*))?"')
TOOLING_RE = re.compile(r"^\^\(feat\|fix\|perf\)\\\(\((?P<items>[a-z0-9|?-]+)\)\\\)$")


def load_scopes(cliff_toml: Path) -> tuple[list[str], list[str]]:
    """Return the area scopes and the tooling scope patterns from `cliff.toml`."""
    config = tomllib.loads(cliff_toml.read_text())
    body = config.get("changelog", {}).get("body", "")
    # An adopted project's own cliff.toml may predate `areas`: it then checks nothing.
    areas_match = AREAS_RE.search(body)
    if areas_match is None:
        return [], []
    items = [item.strip() for item in areas_match["items"].split(",") if item.strip()]
    entries = [AREA_RE.fullmatch(item) for item in items]
    # A skipped entry would leave its scope unchecked, or every scope with no areas.
    bad = [item for item, entry in zip(items, entries, strict=True) if entry is None]
    if bad:
        msg = (
            f'cliff.toml: write each area as "scope" or "scope:Heading", not {bad[0]}.'
        )
        raise ValueError(msg)
    # A cliff.toml body from before cubert 0.2.0 matches "ci:CI" to no commit scope.
    if (
        any(entry and entry["heading"] for entry in entries)
        and "area_scopes" not in body
    ):
        msg = "cliff.toml: a scope:Heading area needs the template's changelog body."
        raise ValueError(msg)
    areas = [entry["scope"] for entry in entries if entry]
    for parser in config.get("git", {}).get("commit_parsers", []):
        tooling_match = TOOLING_RE.match(parser.get("message", ""))
        if tooling_match and parser.get("skip"):
            return areas, tooling_match["items"].split("|")
    return areas, []


def scope_error(message: str, areas: list[str], tooling: list[str]) -> str | None:
    """Return why commit *message* has a wrong changelog scope, or None."""
    subject, _, body = message.partition("\n")
    match = SUBJECT_RE.match(subject)
    if not areas or match is None:
        return None
    # git-cliff lists a breaking commit whatever its type.
    breaking = bool(match["breaking"] or BREAKING_FOOTER_RE.search(body))
    if match["type"] not in CHANGELOG_TYPES and not breaking:
        return None
    scope = match["scope"] or ""
    if scope in areas or any(re.fullmatch(p, scope) for p in tooling):
        return None
    kind = "breaking" if breaking else match["type"]
    error = f"A {kind} commit needs an area scope: {', '.join(areas)}."
    if tooling:
        names = ", ".join(p.replace("?", "") for p in tooling)
        error += f" A fix that users cannot see takes a tooling scope: {names}."
    return error


def main(argv: list[str] | None = None, cliff_toml: Path = Path("cliff.toml")) -> int:
    """Check the subject of a commit message file or of a PR title."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path, help="Commit message file")
    source.add_argument("--subject", help="Commit subject, such as a PR title")
    args = parser.parse_args(argv)

    message = args.subject if args.file is None else args.file.read_text()
    if not cliff_toml.is_file() or re.match(r"^(fixup|squash|amend)! ", message):
        return 0
    try:
        scopes = load_scopes(cliff_toml)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    error = scope_error(message, *scopes)
    if error is None:
        return 0
    print(error, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
