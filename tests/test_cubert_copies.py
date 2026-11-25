"""Check that cubert's copies of template files match the template's."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pr_title_workflow_matches_the_template() -> None:
    # A copy, not a link: GitHub does not follow a symlink in .github/workflows.
    own = (ROOT / ".github/workflows/pr-title.yml").read_text()
    shipped = (ROOT / "template/.github/workflows/pr-title.yml").read_text()

    assert own == shipped


def test_gitignore_holds_every_unconditional_template_entry() -> None:
    # A copy, because the template's file is rendered. Feature blocks do not apply here.
    entries: list[str] = []
    depth = 0
    for line in (ROOT / "template/.gitignore.jinja").read_text().splitlines():
        tag = line.strip()
        if tag.startswith("[% if"):
            depth += 1
        elif tag.startswith("[% endif"):
            depth -= 1
        elif depth == 0 and tag and not tag.startswith("#"):
            entries.append(tag)
    own = set((ROOT / ".gitignore").read_text().splitlines())

    assert [entry for entry in entries if entry not in own] == []


def test_codeowners_matches_the_template() -> None:
    own = (ROOT / ".github/CODEOWNERS").read_text()
    shipped = (ROOT / "template/.github/CODEOWNERS.jinja").read_text()

    assert own == shipped.replace("[[ github_user ]]", "pawelad")


def test_worktrunk_config_matches_the_template_without_feature_blocks() -> None:
    # A copy, because the template's file is rendered. cubert has no OpenTofu.
    shipped, depth = [], 0
    for line in (ROOT / "template/.config/wt.toml.jinja").read_text().splitlines():
        if line.startswith("[% if"):
            depth += 1
        elif line.startswith("[% endif"):
            depth -= 1
        elif depth == 0:
            shipped.append(line)
    own = (ROOT / ".config/wt.toml").read_text().splitlines()

    assert own == shipped
