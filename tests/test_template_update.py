"""Check that `template:update` passes answers to Copier and lists cubert gaps."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from tests.support import ROOT, commit_all, project_env, render_template, run

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


def update(project: Path, tools: Path) -> subprocess.CompletedProcess[str]:
    env = project_env()
    env.update(PATH=f"{tools}{os.pathsep}{env['PATH']}")
    return subprocess.run(  # noqa: S603
        ["bash", str(TASK)],  # noqa: S607
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_update_lists_only_real_cubert_gap_markers(tmp_path: Path) -> None:
    project = render_template(tmp_path)
    run(["git", "-c", "init.defaultBranch=main", "init", "--quiet"], project)
    commit_all(project, "chore: render")
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "copier").write_text("#!/bin/sh\n")
    (tools / "copier").chmod(0o755)

    clean = update(project, tools)

    assert clean.returncode == 0, clean.stderr
    assert "cubert-gap" not in clean.stdout

    hk = project / "hk.pkl"
    hk.write_text(
        f"{hk.read_text()}// cubert-gap: no shared step skips vendored files\n"
    )
    agents = project / "AGENTS.md"
    agents.write_text(
        f"{agents.read_text()}<!-- cubert-gap: no shared commit rule -->\n"
    )
    commit_all(project, "chore: add workarounds")

    marked = update(project, tools)

    assert marked.returncode == 0, marked.stderr
    listed = [line for line in marked.stdout.splitlines() if "cubert-gap:" in line]
    assert len(listed) == 2
    assert any(line.startswith("  hk.pkl:") for line in listed)
    assert any(line.startswith("  AGENTS.md:") for line in listed)
