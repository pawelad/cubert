"""Test the requirements.yml parsing and drift report of check_collections.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support import load_script

check_collections = load_script("template/.config/hk/checks/check_collections.py")
REQUIREMENTS = Path("requirements.yml")


@pytest.mark.parametrize("version", ["1.2.3", "==1.2.3", "1.2.3-beta.1"])
def test_exact_pins_are_accepted(version: str) -> None:
    data = {"collections": [{"name": "demo.util", "version": version}]}

    pins = check_collections.pinned(REQUIREMENTS, data)

    assert pins == {"demo.util": version.removeprefix("==")}


@pytest.mark.parametrize(
    "entry", ["demo.util", {"name": "demo.util"}, {"name": "demo.util", "version": "*"}]
)
def test_unpinned_entries_are_rejected(
    entry: object, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        check_collections.pinned(REQUIREMENTS, {"collections": [entry]})

    assert exit_info.value.code == check_collections.BROKEN
    assert "demo.util needs an exact version" in capsys.readouterr().err


def test_check_lists_each_difference_with_the_fix() -> None:
    pins = {"demo.missing": "1.0.0", "demo.bumped": "2.0.0"}
    found = {"demo.bumped": "1.0.0", "demo.extra": "1.0.0"}

    assert check_collections.problems(pins, found) == [
        "demo.bumped: 1.0.0 installed, pinned 2.0.0",
        "demo.missing: not installed (pinned 1.0.0)",
        "demo.extra: 1.0.0 installed, not in requirements.yml",
    ]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ([{"name": "demo.util", "version": "1.0.0"}], "needs a `collections:` list"),
        ({"collections": "demo.util"}, "needs a `collections:` list"),
        ({"collections": [{"src": "demo.util", "version": "1.0.0"}]}, "None is not"),
        ({"collections": [{"name": "util", "version": "1.0.0"}]}, "'util' is not"),
    ],
)
def test_malformed_requirements_are_rejected(
    data: object, message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        check_collections.pinned(REQUIREMENTS, data)

    assert exit_info.value.code == check_collections.BROKEN
    assert message in capsys.readouterr().err


def test_empty_requirements_pin_nothing() -> None:
    assert check_collections.pinned(REQUIREMENTS, None) == {}
    assert check_collections.pinned(REQUIREMENTS, {"collections": None}) == {}


def test_without_requirements_any_installed_collection_differs(tmp_path: Path) -> None:
    manifest = tmp_path / "collections/ansible_collections/old/gone/MANIFEST.json"
    manifest.parent.mkdir(parents=True)
    info = (
        '{"collection_info": {"namespace": "old", "name": "gone", "version": "1.0.0"}}'
    )
    manifest.write_text(info)

    assert (
        check_collections.main(["--quiet", str(tmp_path)]) == check_collections.DIFFERS
    )
    assert check_collections.main([str(tmp_path / "empty")]) == 0
