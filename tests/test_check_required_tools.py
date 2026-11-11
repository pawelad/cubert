"""Test the check that `mise.toml` configures every tool the shared steps call."""

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
