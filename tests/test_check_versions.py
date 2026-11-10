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

    def test_exact_seed_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "template/.config/hk").mkdir(parents=True)
            (root / "mise.toml").write_text('[tools]\nhk = "2.11.1"\n')
            (root / "template/mise.toml.jinja").write_text('[tools]\njq = "1.8.2"\nhk = "latest"\n')
            (root / "template/.config/hk/base.pkl").write_text("")
            (root / "template/.config/hk/cubert.pkl.jinja").write_text("")
            self.assertEqual(len(check_versions.failures(root)), 1)

    def test_jinja_workflow_must_match_bumped_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "template/.config/hk").mkdir(parents=True)
            (root / "template/.github/workflows").mkdir(parents=True)
            (root / ".github/workflows").mkdir(parents=True)
            (root / "mise.toml").write_text('[tools]\nhk = "2.11.1"\n')
            (root / "template/mise.toml.jinja").write_text("[tools]\n")
            (root / "template/.config/hk/base.pkl").write_text("")
            (root / "template/.config/hk/cubert.pkl.jinja").write_text("")
            (root / ".github/workflows/ci.yml").write_text('- uses: "actions/checkout@v7.0.2"\n')
            jinja = root / "template/.github/workflows/ci.yml.jinja"
            jinja.write_text('- uses: "actions/checkout@v7.0.1"\n- uses: "./.github/actions/setup-mise"\n')
            self.assertEqual(len(check_versions.failures(root)), 1)

    def test_repository_passes(self) -> None:
        self.assertEqual(check_versions.failures(Path()), [])


if __name__ == "__main__":
    unittest.main()
