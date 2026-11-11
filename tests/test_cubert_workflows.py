"""Check that cubert's own workflow copies match the template's."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pr_title_workflow_matches_the_template() -> None:
    # A copy, not a link: GitHub does not follow a symlink in .github/workflows.
    own = (ROOT / ".github/workflows/pr-title.yml").read_text()
    shipped = (ROOT / "template/.github/workflows/pr-title.yml").read_text()

    assert own == shipped
