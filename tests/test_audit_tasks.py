"""Check dependency audits for default projects and adopted backends."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from tests.support import project_env, render_template, run


@pytest.mark.parametrize("scanner_status", [0, 7])
def test_default_project_scans_tool_and_nested_application_lockfiles(
    tmp_path: Path, scanner_status: int
) -> None:
    project = render_template(tmp_path, openspec="none")
    config = tomllib.loads((project / "mise.toml").read_text())
    assert "osv-scanner" in config["tools"]
    required = (project / ".config/mise/required-tools").read_text().splitlines()
    assert "osv-scanner" in required
    run(["git", "init", "--quiet"], project)
    locks = [
        ".mise/locks/pypi-copier/tool/uv.lock",
        "apps/backend/uv.lock",
        "apps/web/bun.lock",
    ]
    for name in locks:
        lock = project / name
        lock.parent.mkdir(parents=True)
        lock.write_text("fixture\n")
    run(["git", "add", "--all"], project)
    tools = tmp_path / "bin"
    tools.mkdir()
    scanner = tools / "osv-scanner"
    scanner.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$SCANNER_CALLS"\nexit "$SCANNER_STATUS"\n'
    )
    scanner.chmod(0o755)
    calls = tmp_path / "scanner-calls"
    env = project_env()
    env.update(
        PATH=f"{tools}{os.pathsep}{env['PATH']}",
        SCANNER_CALLS=str(calls),
        SCANNER_STATUS=str(scanner_status),
    )

    result = subprocess.run(
        ["bash", ".config/mise/tasks/audit/deps"],  # noqa: S607
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == scanner_status, result.stderr
    arguments = calls.read_text().splitlines()
    assert arguments[:2] == ["scan", "source"]
    assert arguments[2::2] == ["--lockfile"] * len(locks)
    assert sorted(arguments[3::2]) == sorted(locks)
