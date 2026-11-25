"""Test the check that `mise.toml` configures every tool the shared steps call."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support import load_script

if TYPE_CHECKING:
    from pathlib import Path

check_required_tools = load_script("template/.config/hk/checks/check_required_tools.py")


def test_configured_tools_pass() -> None:
    config = '[tools]\nhk = { version = "2.11.1" }\n"pypi:copier" = "9.19.1"\n'
    assert check_required_tools.missing("# Comment\nhk\npypi:copier\n", config) == []


def test_missing_tool_fails() -> None:
    missing = check_required_tools.missing("hk\njq\n", '[tools]\nhk = "2.11.1"\n')
    assert missing == ["jq"]


def test_config_without_tools_lists_every_tool() -> None:
    assert check_required_tools.missing("hk\n", "[settings]\n") == ["hk"]


def test_names_mode_prints_missing_tools_and_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".config/mise").mkdir(parents=True)
    (tmp_path / ".config/mise/required-tools").write_text("hk\njq\nuv\n")
    (tmp_path / "mise.toml").write_text('[tools]\nhk = "2.11.1"\n')
    monkeypatch.chdir(tmp_path)
    status = check_required_tools.main(["--names"])
    assert (status, capsys.readouterr().out) == (0, "jq\nuv\n")


def test_tool_below_its_minimum_fails() -> None:
    old = check_required_tools.outdated("hk>=2.11.1\n", '[tools]\nhk = "1.51.0"\n')
    assert old == [("hk", "2.11.1", "1.51.0")]


def test_tool_at_or_above_its_minimum_passes() -> None:
    required = "hk>=2.11.1\njq>=1.7\n"
    config = '[tools]\nhk = { version = "2.11.1" }\njq = "1.10.0"\n'
    assert check_required_tools.outdated(required, config) == []


def test_unpinned_tool_is_not_compared() -> None:
    config = '[tools]\nhk = "latest"\n'
    assert check_required_tools.outdated("hk>=2.11.1\n", config) == []


def test_minimum_is_not_part_of_the_tool_name() -> None:
    config = '[tools]\nhk = "2.11.1"\n'
    assert check_required_tools.missing("hk>=2.11.1\n", config) == []


def test_names_mode_keeps_the_minimum_of_a_missing_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".config/mise").mkdir(parents=True)
    (tmp_path / ".config/mise/required-tools").write_text("fnox>=1.50.0\nuv\n")
    (tmp_path / "mise.toml").write_text('[tools]\nuv = "1.0.0"\n')
    monkeypatch.chdir(tmp_path)
    status = check_required_tools.main(["--names"])
    assert (status, capsys.readouterr().out) == (0, "fnox>=1.50.0\n")


def test_names_mode_prints_the_pinned_minimum_of_an_outdated_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".config/mise").mkdir(parents=True)
    (tmp_path / ".config/mise/required-tools").write_text("hk>=2.11.1\njq\n")
    (tmp_path / "mise.toml").write_text('[tools]\nhk = "1.51.0"\n')
    monkeypatch.chdir(tmp_path)
    status = check_required_tools.main(["--names"])
    assert (status, capsys.readouterr().out) == (0, "jq\nhk@2.11.1\n")


def test_check_mode_names_the_outdated_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".config/mise").mkdir(parents=True)
    (tmp_path / ".config/mise/required-tools").write_text("hk>=2.11.1\n")
    (tmp_path / "mise.toml").write_text('[tools]\nhk = "1.51.0"\n')
    monkeypatch.chdir(tmp_path)
    status = check_required_tools.main([])
    out = capsys.readouterr().out
    assert status == 1
    assert "hk 1.51.0 is below 2.11.1" in out
    assert "Fix: mise run setup" in out


def test_names_mode_adds_a_tool_from_its_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".config/mise").mkdir(parents=True)
    required = "node@lts\nnpm:@fission-ai/openspec\n"
    (tmp_path / ".config/mise/required-tools").write_text(required)
    (tmp_path / "mise.toml").write_text("[tools]\n")
    monkeypatch.chdir(tmp_path)
    status = check_required_tools.main(["--names"])
    assert (status, capsys.readouterr().out) == (
        0,
        "node@lts\nnpm:@fission-ai/openspec\n",
    )


def test_channel_is_not_part_of_the_tool_name() -> None:
    config = '[tools]\nnode = "24.11.0"\n'
    assert check_required_tools.missing("node@lts\n", config) == []


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ('"9.19.1"', ["pypi:copier[python=3.14]@9.19.1"]),
        (
            '{ version = "9.19.1", python = "3.12" }',
            ["pypi:copier[python=3.14]@9.19.1"],
        ),
        ('{ version = "9.19.1", python = "3.14" }', []),
        (
            '["9.19.1", "9.18.0"]',
            [
                "pypi:copier[python=3.14]@9.19.1",
                "pypi:copier[python=3.14]@9.18.0",
            ],
        ),
    ],
)
def test_runtime_repairs_preserve_configured_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    configured: str,
    expected: list[str],
) -> None:
    (tmp_path / ".config/mise").mkdir(parents=True)
    (tmp_path / ".config/mise/required-tools").write_text("pypi:copier[python=3.14]\n")
    (tmp_path / "mise.toml").write_text(f'[tools]\n"pypi:copier" = {configured}\n')
    monkeypatch.chdir(tmp_path)
    assert check_required_tools.main(["--names"]) == 0
    assert capsys.readouterr().out.split() == expected


def test_seeded_inline_options_can_put_the_version_in_any_position() -> None:
    config = '[tools]\nyamllint = { python = "3.14", version = "latest" }\n'
    assert check_required_tools.unpinned(config) == ["yamllint@latest"]


def test_seeded_version_list_preserves_its_pinned_versions() -> None:
    config = '[tools]\nnode = ["24.22.2", "lts"]\n'
    assert check_required_tools.unpinned(config) == ["node@24.22.2", "node@lts"]


def test_seeded_latest_tool_carries_its_minimum() -> None:
    config = '[tools]\nfnox = "latest"\n'
    assert check_required_tools.unpinned(config, "fnox>=1.50.0\n") == [
        "fnox@latest>=1.50.0"
    ]


def test_missing_tool_retains_its_private_runtime_selector() -> None:
    assert check_required_tools.missing("yamllint[python=3.14]\n", "[tools]\n") == [
        "yamllint"
    ]
