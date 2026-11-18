"""Check cache initialization before OpenTofu reads its configuration."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.support import project_env, render_template


@pytest.mark.parametrize("task", ["check/opentofu", "opentofu/lock", "opentofu/init"])
def test_task_creates_a_missing_provider_cache(tmp_path: Path, task: str) -> None:
    project = render_template(tmp_path, opentofu="true", openspec="none")
    script = (project / ".config/mise/tasks" / task).read_text()
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "tofu").write_text('#!/bin/sh\n[ -d "$TF_PLUGIN_CACHE_DIR" ] || exit 9\n')
    (tools / "tofu").chmod(0o755)
    cache = tmp_path / "missing/cache"
    env = project_env()
    env.update(
        PATH=f"{tools}{os.pathsep}{env['PATH']}",
        TF_PLUGIN_CACHE_DIR=str(cache),
        usage_upgrade="true",
        # Skip the mise exec rerun that loads the OpenTofu env.
        OPENTOFU_TASK_ENV="1",
    )

    result = subprocess.run(  # noqa: S603
        ["bash", "-c", script],  # noqa: S607
        cwd=project / "opentofu",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert cache.is_dir()
