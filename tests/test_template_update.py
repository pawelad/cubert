"""Check that `template:update` passes changed answers to Copier."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.support import ROOT, project_env, run

TASK = ROOT / "template/.config/mise/tasks/template/update"


def test_update_passes_each_answer_as_one_copier_argument(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "-c", "init.defaultBranch=main", "init", "--quiet"], repo)
    calls = tmp_path / "calls"
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "copier").write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {calls}\n')
    (tools / "copier").chmod(0o755)
    env = project_env()
    env.update(
        PATH=f"{tools}{os.pathsep}{env['PATH']}",
        # The format mise uses for a repeated flag, with a value that a shell would run.
        usage_data="'secrets_provider=proton-pass' 'secrets_vault=it'\\''s $(id)'",
    )

    result = subprocess.run(  # noqa: S603
        ["bash", str(TASK)],  # noqa: S607
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert calls.read_text().splitlines()[-4:] == [
        "--data",
        "secrets_provider=proton-pass",
        "--data",
        "secrets_vault=it's $(id)",
    ]
