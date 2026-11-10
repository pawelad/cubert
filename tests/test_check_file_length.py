"""Test the file-length check that hk runs on source and test files."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.support import load_script

check_file_length = load_script("template/.config/hk/checks/check_file_length.py")
MAX = check_file_length.MAX_FILE_LINES


class CheckFileLengthTest(unittest.TestCase):
    def run_on(self, name: str, lines: int) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_text("x = 1\n" * lines)
            return check_file_length.main([str(path)])

    def test_file_at_the_cap_passes(self) -> None:
        self.assertEqual(self.run_on("a.py", MAX), 0)

    def test_file_over_the_cap_fails(self) -> None:
        self.assertEqual(self.run_on("a.tsx", MAX + 1), 1)

    def test_other_extensions_are_skipped(self) -> None:
        self.assertEqual(self.run_on("a.md", MAX + 1), 0)

    def test_missing_file_is_skipped(self) -> None:
        self.assertEqual(check_file_length.main(["does-not-exist.py"]), 0)


if __name__ == "__main__":
    unittest.main()
