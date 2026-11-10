"""Test that cubert's own pins match the pins that the template ships."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("check_versions", Path("scripts/check_versions.py"))
assert spec and spec.loader
check_versions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_versions)


class CheckVersionsTest(unittest.TestCase):
    def test_template_tools_reads_every_feature_block(self) -> None:
        text = '[tools]\nhk = "1"\n[% if python %]\nruff = "2"\n[% endif %]\n\n[tasks.x]\nrun = "y"\n'
        self.assertEqual(check_versions.template_tools(text), {"hk": "1", "ruff": "2"})

    def test_repository_pins_agree(self) -> None:
        self.assertEqual(check_versions.failures(Path()), [])


if __name__ == "__main__":
    unittest.main()
