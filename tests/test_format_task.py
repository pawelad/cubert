"""Check that format skips each hk step that has no fix command."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "template/.config/mise/tasks/format"


def run_task(
    tmp_path: Path,
    *,
    check_only: tuple[str, ...] = (),
    usage_all: bool = False,
    pkl_fails: bool = False,
    real_pkl: bool = False,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run the format task with a stubbed hk, returning result and hk args."""
    tools = tmp_path / "bin"
    tools.mkdir()
    calls = tmp_path / "calls"
    calls.touch()
    (tools / "hk").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n')
    (tools / "hk").chmod(0o755)
    if not real_pkl:
        names = "".join(f"{name}\\n" for name in check_only)
        pkl = "exit 1" if pkl_fails else f"printf '{names}'"
        (tools / "pkl").write_text(f"#!/bin/sh\n{pkl}\n")
        (tools / "pkl").chmod(0o755)
        (tmp_path / "hk.pkl").write_text("// stub\n")
    env = dict(os.environ)
    env.update(PATH=f"{tools}{os.pathsep}{os.environ['PATH']}", CALLS=str(calls))
    if usage_all:
        env["usage_all"] = "true"
    else:
        env.pop("usage_all", None)
    cwd = ROOT if real_pkl else tmp_path
    result = subprocess.run(  # noqa: S603
        [TASK], cwd=cwd, env=env, capture_output=True, text=True, check=False
    )
    return result, calls.read_text().splitlines()


def test_skips_each_step_that_has_no_fix_command(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, check_only=("tsc", "expo-types"))

    assert result.returncode == 0, result.stderr
    assert calls == ["fix --no-fail-fast --skip-step tsc --skip-step expo-types"]


def test_omits_skip_step_when_every_step_has_a_fix_command(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path)

    assert result.returncode == 0, result.stderr
    assert calls == ["fix --no-fail-fast"]


def test_all_flag_passes_all_to_hk_fix(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, check_only=("tsc",), usage_all=True)

    assert result.returncode == 0, result.stderr
    assert calls == ["fix --no-fail-fast --all --skip-step tsc"]


def test_runs_hk_fix_without_skip_step_when_pkl_fails(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, check_only=("tsc",), pkl_fails=True)

    assert result.returncode == 0, result.stderr
    assert "pkl cannot list the steps" in result.stderr
    assert calls == ["fix --no-fail-fast"]


@pytest.mark.skipif(shutil.which("pkl") is None, reason="needs pkl on PATH")
def test_hk_config_query_selects_only_check_only_steps(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, real_pkl=True)

    assert result.returncode == 0, result.stderr
    skipped = calls[0].split(" --skip-step ")[1:]
    assert "shellcheck" in skipped
    assert "typos" in skipped
    assert "dprint" not in skipped
    assert "no-em-dashes" not in skipped
