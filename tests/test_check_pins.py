"""Test the pins check that hk runs on mise.toml."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support import load_script

if TYPE_CHECKING:
    from pathlib import Path

check_pins = load_script("template/.config/hk/checks/check_pins.py")


def run_on(tmp_path: Path, name: str, text: str) -> int:
    path = tmp_path / name
    path.write_text(text)
    return check_pins.main([str(path)])


def test_mise_exact_version_passes(tmp_path: Path) -> None:
    assert run_on(tmp_path, "mise.toml", '[tools]\nhk = "2.11.1"\n') == 0


def test_mise_latest_fails(tmp_path: Path) -> None:
    assert run_on(tmp_path, "mise.toml", '[tools]\nhk = "latest"\n') == 1


def test_mise_lts_fails(tmp_path: Path) -> None:
    assert run_on(tmp_path, "mise.toml", '[tools]\nnode = "lts"\n') == 1
