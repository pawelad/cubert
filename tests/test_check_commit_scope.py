"""Test the changelog scope check against the template's cliff.toml."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support import ROOT, load_script

if TYPE_CHECKING:
    from pathlib import Path

check = load_script("template/.config/hk/checks/check_commit_scope.py")
CLIFF = (ROOT / "template/[% if changelog %]cliff.toml[% endif %].jinja").read_text()


def cliff_with_areas(tmp_path: Path, areas: str) -> Path:
    path = tmp_path / "cliff.toml"
    path.write_text(
        CLIFF.replace("{% set areas = [] %}", f"{{% set areas = [{areas}] %}}")
    )
    return path


def run(tmp_path: Path, cliff: Path, subject: str) -> int:
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text(f"{subject}\n\nBody.\n")
    return check.main(["--file", str(message)], cliff_toml=cliff)


def test_reads_areas_and_tooling_scopes(tmp_path: Path) -> None:
    areas, tooling = check.load_scopes(cliff_with_areas(tmp_path, '"map", "spots"'))
    assert areas == ["map", "spots"]
    assert "ci" in tooling


@pytest.mark.parametrize(
    "subject",
    [
        "feat(spots): let founders suggest a name",
        "fix(ci): pin the runner",
        "fix(tests): stabilize the map test",
        "fix(map)!: drop the legacy style",
        "refactor(map)!: drop the legacy style",
        "fix(ci)!: drop an old hook",
        "refactor(frontend): split the card",
        "chore: bump dependencies",
        "fixup! fix: rename a spot",
    ],
)
def test_accepts_area_tooling_and_non_changelog_subjects(
    tmp_path: Path, subject: str
) -> None:
    assert run(tmp_path, cliff_with_areas(tmp_path, '"map", "spots"'), subject) == 0


@pytest.mark.parametrize(
    "subject",
    [
        "feat(frontend): add a button",
        "fix: rename a spot",
        "perf(spot): cache the card",
        "refactor(frontend)!: drop the legacy card",
        "refactor: drop the legacy card\n\nBREAKING CHANGE: the card is gone",
    ],
)
def test_rejects_changelog_subjects_without_an_area(
    tmp_path: Path, subject: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(tmp_path, cliff_with_areas(tmp_path, '"map", "spots"'), subject) == 1
    assert "commit needs an area scope: map, spots" in capsys.readouterr().err


def test_cubert_lists_agent_rules_and_hides_only_docs_and_e2e() -> None:
    areas, tooling = check.load_scopes(ROOT / "cliff.toml")
    assert "agents" in areas
    assert tooling == ["docs", "e2e"]


def test_reads_the_scope_of_an_area_with_a_heading(tmp_path: Path) -> None:
    cliff = cliff_with_areas(tmp_path, '"map", "ci:CI", "tofu:OpenTofu"')
    areas, _ = check.load_scopes(cliff)
    assert areas == ["map", "ci", "tofu"]


@pytest.mark.parametrize("areas", ["'map'", '"Map"', '"map:"', '"open_tofu:OpenTofu"'])
def test_rejects_a_malformed_area_instead_of_skipping_it(
    tmp_path: Path, areas: str
) -> None:
    cliff = cliff_with_areas(tmp_path, f'"spots", {areas}')
    assert run(tmp_path, cliff, "feat(spots): add a thing") == 1


def test_rejects_a_heading_area_with_a_body_from_before_headings(
    tmp_path: Path,
) -> None:
    cliff = cliff_with_areas(tmp_path, '"map", "ci:CI"')
    cliff.write_text(cliff.read_text().replace("area_scopes", "areas"))
    assert run(tmp_path, cliff, "feat(map): add a thing") == 1


def test_template_default_has_no_areas_and_accepts_any_scope(tmp_path: Path) -> None:
    path = tmp_path / "cliff.toml"
    path.write_text(CLIFF)
    assert run(tmp_path, path, "feat(anything): add a button") == 0


def test_a_project_cliff_toml_without_areas_passes(tmp_path: Path) -> None:
    path = tmp_path / "cliff.toml"
    path.write_text('[changelog]\nbody = "{{ version }}"\n')
    assert run(tmp_path, path, "fix: rename a spot") == 0


def test_no_cliff_toml_passes(tmp_path: Path) -> None:
    assert run(tmp_path, tmp_path / "cliff.toml", "fix: rename a spot") == 0
