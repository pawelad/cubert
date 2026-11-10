"""Test the comment-length check that hk runs on Python and TypeScript files."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.support import load_script

check_comment_length = load_script("template/.config/hk/checks/check_comment_length.py")
MAX = check_comment_length.MAX_PROSE_LINES


def prose(count: int, prefix: str = "") -> str:
    return "".join(f"{prefix}Line {number}.\n" for number in range(count))


class CheckCommentLengthTest(unittest.TestCase):
    def run_on(self, name: str, text: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_text(text)
            return check_comment_length.main([str(path)])

    def test_docstring_at_the_cap_passes(self) -> None:
        self.assertEqual(self.run_on("a.py", f'def f():\n    """{prose(MAX)}"""\n'), 0)

    def test_docstring_over_the_cap_fails(self) -> None:
        self.assertEqual(self.run_on("a.py", f'def f():\n    """{prose(MAX + 1)}"""\n'), 1)

    def test_docstring_sections_do_not_count(self) -> None:
        text = f'def f(x):\n    """{prose(MAX)}\n    Args:\n{prose(MAX, "        ")}    """\n'
        self.assertEqual(self.run_on("a.py", text), 0)

    def test_hash_comment_block_over_the_cap_fails(self) -> None:
        self.assertEqual(self.run_on("a.py", prose(MAX + 1, "# ")), 1)

    def test_directives_and_shebang_do_not_count(self) -> None:
        text = "#!/usr/bin/env python\n" + prose(MAX, "# ") + "# noqa: E501\n# type: ignore\n"
        self.assertEqual(self.run_on("a.py", text), 0)

    def test_fenced_code_does_not_count(self) -> None:
        text = f'"""{prose(MAX)}\n```\n{prose(MAX)}```\n"""\n'
        self.assertEqual(self.run_on("a.py", text), 0)

    def test_ts_line_comments_over_the_cap_fail(self) -> None:
        self.assertEqual(self.run_on("a.ts", prose(MAX + 1, "// ") + "const x = 1;\n"), 1)

    def test_jsdoc_tags_do_not_count(self) -> None:
        text = "/**\n" + prose(MAX, " * ") + prose(MAX, " * @param x ") + " */\n"
        self.assertEqual(self.run_on("a.ts", text), 0)

    def test_jsdoc_over_the_cap_fails(self) -> None:
        self.assertEqual(self.run_on("a.ts", "/**\n" + prose(MAX + 1, " * ") + " */\n"), 1)

    def test_other_extensions_are_skipped(self) -> None:
        self.assertEqual(self.run_on("a.sh", prose(MAX + 1, "# ")), 0)


if __name__ == "__main__":
    unittest.main()
