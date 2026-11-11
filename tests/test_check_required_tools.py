"""Test the check that `mise.toml` configures every tool the shared steps call."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support import load_script

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

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
