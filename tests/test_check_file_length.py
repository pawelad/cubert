"""Test the file-length check that hk runs on source and test files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support import load_script

if TYPE_CHECKING:
    from pathlib import Path

check_file_length = load_script("template/.config/hk/checks/check_file_length.py")
MAX = check_file_length.MAX_FILE_LINES


def run_on(tmp_path: Path, name: str, lines: int) -> int:
    path = tmp_path / name
    path.write_text("x = 1\n" * lines)
    return check_file_length.main([str(path)])


def test_file_at_the_cap_passes(tmp_path: Path) -> None:
    assert run_on(tmp_path, "a.py", MAX) == 0


def test_file_over_the_cap_fails(tmp_path: Path) -> None:
    assert run_on(tmp_path, "a.tsx", MAX + 1) == 1


def test_other_extensions_are_skipped(tmp_path: Path) -> None:
    assert run_on(tmp_path, "a.md", MAX + 1) == 0


def test_missing_file_is_skipped() -> None:
    assert check_file_length.main(["does-not-exist.py"]) == 0
