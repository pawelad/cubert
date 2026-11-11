"""Check selected-file routing and package test script dispatch."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import project_env, render_template


@pytest.mark.parametrize(
    "directory", ["apps/web", "./apps/web", "apps/web/", ".", "./"]
)
@pytest.mark.parametrize("script", [False, True])
def test_selected_file_runs_in_its_package(
    tmp_path: Path, directory: str, script: bool
) -> None:
    project = render_template(
        tmp_path,
        typescript="true",
        typescript_dirs=json.dumps([directory]),
        openspec="none",
    )
    package = project / directory
    package.mkdir(parents=True, exist_ok=True)
    data = {"scripts": {"test": "vitest run"}} if script else {}
    (package / "package.json").write_text(json.dumps(data))
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "bun").write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" "$*" > "$BUN_CALLS"\n')
    (tools / "bun").chmod(0o755)
    calls = tmp_path / "bun-calls"
    env = project_env()
    relative = (
        "example.test.ts" if directory in {".", "./"} else "apps/web/example.test.ts"
    )
    env.update(
        PATH=f"{tools}{os.pathsep}{env['PATH']}",
        BUN_CALLS=str(calls),
        usage_files=f"./{relative}",
    )

    result = subprocess.run(
        ["bash", ".config/mise/tasks/test/typescript"],  # noqa: S607
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    called_directory, command = calls.read_text().splitlines()
    assert Path(called_directory).resolve() == package.resolve()
    prefix = "run test" if script else "test --pass-with-no-tests"
    assert command == f"{prefix} ./example.test.ts"

    env["usage_files"] = "unconfigured/example.test.ts"
    # A root package owns every relative file, so use the subdirectory cases here.
    if directory not in {".", "./"}:
        calls.unlink()
        result = subprocess.run(
            ["bash", ".config/mise/tasks/test/typescript"],  # noqa: S607
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        assert "no selected files belong to a configured package" in result.stderr
        assert not calls.exists()
