"""Test the check that `mise.toml` configures every tool the shared steps call."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from tests.support import load_script

check_required_tools = load_script("template/.config/hk/checks/check_required_tools.py")


class CheckRequiredToolsTest(unittest.TestCase):
    def test_configured_tools_pass(self) -> None:
        config = '[tools]\nhk = { version = "2.11.1" }\n"pypi:copier" = "9.19.1"\n'
        self.assertEqual(
            check_required_tools.missing("# Comment\nhk\npypi:copier\n", config), []
        )

    def test_missing_tool_fails(self) -> None:
        self.assertEqual(
            check_required_tools.missing("hk\njq\n", '[tools]\nhk = "2.11.1"\n'), ["jq"]
        )

    def test_config_without_tools_lists_every_tool(self) -> None:
        self.assertEqual(check_required_tools.missing("hk\n", "[settings]\n"), ["hk"])

    def test_names_mode_prints_missing_tools_and_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".config/mise").mkdir(parents=True)
            (root / ".config/mise/required-tools").write_text("hk\njq\nuv\n")
            (root / "mise.toml").write_text('[tools]\nhk = "2.11.1"\n')
            out = io.StringIO()
            cwd = Path.cwd()
            os.chdir(root)
            try:
                with contextlib.redirect_stdout(out):
                    status = check_required_tools.main(["--names"])
            finally:
                os.chdir(cwd)
        self.assertEqual((status, out.getvalue()), (0, "jq\nuv\n"))


if __name__ == "__main__":
    unittest.main()
