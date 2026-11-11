"""Test that the template seeds no tool versions, and that the hk package matches hk."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.support import load_script

check_versions = load_script("scripts/check_versions.py")


class CheckVersionsTest(unittest.TestCase):
    def test_template_tools_reads_every_feature_block(self) -> None:
        text = '[tools]\nhk = "1"\n[% if python %]\nruff = "2"\n[% endif %]\n\n[tasks.x]\nrun = "y"\n'
        self.assertEqual(check_versions.template_tools(text), {"hk": "1", "ruff": "2"})

    def failures_in(self, files: dict[str, str]) -> list[str]:
        """Run the check on a minimal repository, with `files` added or replaced."""
        base = {
            "mise.toml": '[tools]\nhk = "2.11.1"\n',
            "template/mise.toml.jinja": '[tools]\nhk = "latest"\n',
            "template/.config/hk/base.pkl": "",
            "template/.config/hk/cubert.pkl.jinja": "",
            "template/.config/mise/required-tools.jinja": "hk\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, text in (base | files).items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(text)
            return check_versions.failures(root)

    def test_minimal_repository_passes(self) -> None:
        self.assertEqual(self.failures_in({}), [])

    def test_exact_seed_fails(self) -> None:
        files = {
            "template/mise.toml.jinja": '[tools]\njq = "1.8.2"\nnode = "lts"\n',
            "template/.config/mise/required-tools.jinja": "jq\nnode\n",
        }
        self.assertEqual(len(self.failures_in(files)), 1)

    def test_required_tools_read_every_feature_block(self) -> None:
        text = "# Comment\nhk\n[% if python %]\nruff\n[% endif %]\n"
        self.assertEqual(check_versions.required_tools(text), {"hk", "ruff"})

    def test_seeded_tool_must_be_required(self) -> None:
        files = {"template/mise.toml.jinja": '[tools]\nhk = "latest"\njq = "latest"\n'}
        self.assertEqual(len(self.failures_in(files)), 1)

    def test_hk_package_must_match_hk(self) -> None:
        url = "package://github.com/jdx/hk/releases/download/v2.10.0/hk@2.10.0#/Config.pkl"
        self.assertEqual(len(self.failures_in({"template/.config/hk/base.pkl": url})), 1)

    def test_jinja_workflow_must_match_bumped_action(self) -> None:
        files = {
            ".github/workflows/ci.yml": '- uses: "actions/checkout@v7.0.2"\n',
            "template/.github/workflows/ci.yml.jinja": (
                '- uses: "actions/checkout@v7.0.1"\n- uses: "./.github/actions/setup-mise"\n'
            ),
        }
        self.assertEqual(len(self.failures_in(files)), 1)

    def test_repository_passes(self) -> None:
        self.assertEqual(check_versions.failures(Path()), [])


if __name__ == "__main__":
    unittest.main()
