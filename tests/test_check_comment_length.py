"""Test the comment-length check that hk runs on Python and TypeScript files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support import load_script

if TYPE_CHECKING:
    from pathlib import Path

check_comment_length = load_script("template/.config/hk/checks/check_comment_length.py")
MAX = check_comment_length.MAX_PROSE_LINES


def prose(count: int, prefix: str = "") -> str:
    return "".join(f"{prefix}Line {number}.\n" for number in range(count))


def run_on(tmp_path: Path, name: str, text: str) -> int:
    path = tmp_path / name
    path.write_text(text)
    return check_comment_length.main([str(path)])


def test_docstring_at_the_cap_passes(tmp_path: Path) -> None:
    text = f'def f():\n    """{prose(MAX)}"""\n'
    assert run_on(tmp_path, "a.py", text) == 0


def test_docstring_over_the_cap_fails(tmp_path: Path) -> None:
    text = f'def f():\n    """{prose(MAX + 1)}"""\n'
    assert run_on(tmp_path, "a.py", text) == 1


def test_docstring_sections_do_not_count(tmp_path: Path) -> None:
    args = prose(MAX, "        ")
    text = f'def f(x):\n    """{prose(MAX)}\n    Args:\n{args}    """\n'
    assert run_on(tmp_path, "a.py", text) == 0


def test_hash_comment_block_over_the_cap_fails(tmp_path: Path) -> None:
    assert run_on(tmp_path, "a.py", prose(MAX + 1, "# ")) == 1


def test_directives_and_shebang_do_not_count(tmp_path: Path) -> None:
    text = (
        "#!/usr/bin/env python\n" + prose(MAX, "# ") + "# noqa: E501\n# type: ignore\n"
    )
    assert run_on(tmp_path, "a.py", text) == 0


def test_fenced_code_does_not_count(tmp_path: Path) -> None:
    text = f'"""{prose(MAX)}\n```\n{prose(MAX)}```\n"""\n'
    assert run_on(tmp_path, "a.py", text) == 0


def test_ts_line_comments_over_the_cap_fail(tmp_path: Path) -> None:
    text = prose(MAX + 1, "// ") + "const x = 1;\n"
    assert run_on(tmp_path, "a.ts", text) == 1


def test_jsdoc_tags_do_not_count(tmp_path: Path) -> None:
    text = "/**\n" + prose(MAX, " * ") + prose(MAX, " * @param x ") + " */\n"
    assert run_on(tmp_path, "a.ts", text) == 0


def test_jsdoc_over_the_cap_fails(tmp_path: Path) -> None:
    text = "/**\n" + prose(MAX + 1, " * ") + " */\n"
    assert run_on(tmp_path, "a.ts", text) == 1


def test_other_extensions_are_skipped(tmp_path: Path) -> None:
    assert run_on(tmp_path, "a.sh", prose(MAX + 1, "# ")) == 0
