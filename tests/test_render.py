"""Check that answers with quotes and backslashes render into valid files."""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest

from tests.support import render_template, run

pytestmark = pytest.mark.skipif(
    shutil.which("copier") is None, reason="needs copier on PATH"
)

TRICKY = 'A "quoted" project with a \\ backslash.'


def test_description_with_quotes_renders_valid_pyproject(tmp_path: Path) -> None:
    project = render_template(tmp_path, python="true", description=TRICKY)

    parsed = tomllib.loads((project / "pyproject.toml").read_text())

    assert parsed["project"]["description"] == TRICKY


def test_hooks_install_keeps_a_post_checkout_hook_that_is_not_cubert(
    tmp_path: Path,
) -> None:
    project = render_template(tmp_path)
    run(["git", "init", "--quiet", "--initial-branch", "main"], project)
    foreign = project / ".git/hooks/post-checkout"
    foreign.write_text("#!/bin/sh\necho mine\n")

    run(["bash", ".config/mise/tasks/hooks/install"], project)

    assert foreign.read_text() == "#!/bin/sh\necho mine\n"
    ours = foreign.parent / "post-checkout.cubert"
    assert "mise run worktree:setup" in ours.read_text()


def test_hooks_install_replaces_its_own_post_checkout_hook(tmp_path: Path) -> None:
    project = render_template(tmp_path)
    run(["git", "init", "--quiet", "--initial-branch", "main"], project)

    run(["bash", ".config/mise/tasks/hooks/install"], project)
    run(["bash", ".config/mise/tasks/hooks/install"], project)

    hooks = project / ".git/hooks"
    assert "mise run worktree:setup" in (hooks / "post-checkout").read_text()
    assert not (hooks / "post-checkout.cubert").exists()
