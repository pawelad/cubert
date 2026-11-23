"""Check that the shared test task runs every suite and takes no arguments."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

TASK = Path("template/.config/mise/tasks/test/_default").resolve()

STUB_MISE = """#!/bin/sh
printf '%s\\n' "$*" >> "$CALLS"
case "$1" in
  tasks) printf 'check\\n' ;;
esac
case "$1 $HIDDEN_ONLY" in
  "tasks ") printf 'test:python  Run the Python tests\\n' ;;
  "tasks 1") case "$*" in *" --hidden"*) printf 'test:hidden\\n' ;; esac ;;
esac
"""


def run_task(
    tmp_path: Path, *args: str, hidden_only: bool = False
) -> tuple[subprocess.CompletedProcess[str], str]:
    """Run the task with a stub mise, and return the result and the mise calls."""
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "mise").write_text(STUB_MISE)
    (tools / "mise").chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    env = {**os.environ, "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"}
    env["CALLS"] = str(calls)
    env["HIDDEN_ONLY"] = "1" if hidden_only else ""
    result = subprocess.run(  # noqa: S603
        [TASK, *args], env=env, capture_output=True, text=True, check=False
    )
    return result, calls.read_text()


def test_file_argument_fails_without_running_a_suite(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, "tests/test_example.py")

    assert result.returncode == 2
    assert "mise run test:<area> <file>" in result.stderr
    assert calls == ""


def test_no_argument_runs_every_test_task(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path)

    assert result.returncode == 0, result.stderr
    assert calls.splitlines()[-1] == "run test:*"


def test_hidden_test_task_counts_as_a_suite(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, hidden_only=True)

    assert result.returncode == 0, result.stderr
    assert calls.splitlines()[-1] == "run test:*"
