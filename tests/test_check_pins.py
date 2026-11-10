"""Test the pins check that hk runs on mise.toml and GitHub workflows."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.support import load_script

check_pins = load_script("template/.config/hk/checks/check_pins.py")


class CheckPinsTest(unittest.TestCase):
    def run_on(self, name: str, text: str) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_text(text)
            return check_pins.main([str(path)])

    def test_mise_exact_version_passes(self) -> None:
        self.assertEqual(self.run_on("mise.toml", '[tools]\nhk = "2.11.1"\n'), 0)

    def test_mise_latest_fails(self) -> None:
        self.assertEqual(self.run_on("mise.toml", '[tools]\nhk = "latest"\n'), 1)

    def test_action_full_tag_and_sha_pass(self) -> None:
        sha = "a" * 40
        text = f'steps:\n  - uses: "actions/checkout@v7.0.1"\n  - uses: "x/y@{sha}"\n  - uses: "./local"\n'
        self.assertEqual(self.run_on("ci.yml", text), 0)

    def test_action_major_tag_fails(self) -> None:
        self.assertEqual(self.run_on("ci.yml", 'steps:\n  - uses: "actions/checkout@v7"\n'), 1)


if __name__ == "__main__":
    unittest.main()
