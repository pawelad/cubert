"""Keep nested render tasks independent of the enclosing project's mise config."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.support import ROOT, project_env


def test_relative_output_does_not_inherit_parent_tasks(tmp_path: Path) -> None:
    (tmp_path / "mise.toml").write_text('[tasks.parent-only]\nrun = "exit 9"\n')
    project = tmp_path / "out/project"
    project.mkdir(parents=True)
    (project / "mise.toml").write_text('[tasks.child-only]\nrun = "exit 0"\n')
    env = project_env()
    env.update(
        HELPER=str(ROOT / "scripts/e2e_env.sh"),
        MISE_TRUSTED_CONFIG_PATHS=str(tmp_path),
    )

    result = subprocess.run(
        [  # noqa: S607
            "bash",
            "-c",
            'out=out; source "$HELPER"; cd "$out/project"; mise tasks ls --no-header',
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "child-only" in result.stdout
    assert "parent-only" not in result.stdout
