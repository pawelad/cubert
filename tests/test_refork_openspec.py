"""Test that the refork script turns the pinned spec-driven schema into the fork."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import load_script

refork = load_script("scripts/refork_openspec.py")
FORK = Path("template/openspec/schemas/changes-only")


def upstream_schema_dir() -> Path | None:
    """Return the spec-driven schema in the pinned OpenSpec, if it is installed."""
    mise = shutil.which("mise")
    if not mise:
        return None
    where = subprocess.run(  # noqa: S603 - fixed arguments
        [mise, "where", "npm:@fission-ai/openspec"],
        capture_output=True,
        text=True,
        check=False,
    )
    if where.returncode != 0:
        return None
    return next(
        Path(where.stdout.strip()).glob("**/@fission-ai/openspec/schemas/spec-driven"),
        None,
    )


def as_forked(text: str) -> str:
    """Apply the two edits that `openspec schema fork` makes: name and list spacing."""
    text = re.sub(
        r"^name: spec-driven$", "name: changes-only", text, count=1, flags=re.MULTILINE
    )
    return re.sub(
        r"^(\s*\w+: )\[([^\]\s][^\]\n]*[^\]\s]|[^\]\s])\]$",
        r"\1[ \2 ]",
        text,
        flags=re.MULTILINE,
    )


def test_unmatched_edit_fails_loudly() -> None:
    with pytest.raises(SystemExit):
        refork.transform_schema("name: spec-driven\ndescription: x\n")


def test_proposal_template_drops_capabilities() -> None:
    text = "## Why\n\nx\n\n## Capabilities\n\ny\n\n## Impact\n\nz\n"
    assert refork.transform_proposal_template(text) == "## Why\n\nx\n\n## Impact\n\nz\n"


def test_pinned_upstream_matches_the_committed_fork() -> None:
    upstream = upstream_schema_dir()
    if upstream is None:
        pytest.skip("the pinned OpenSpec is not installed")
    schema = refork.transform_schema((upstream / "schema.yaml").read_text())
    assert as_forked(schema) == (FORK / "schema.yaml").read_text()
    proposal = refork.transform_proposal_template(
        (upstream / "templates/proposal.md").read_text()
    )
    assert proposal == (FORK / "templates/proposal.md").read_text()
