"""Check that format skips tsc only when hk.pkl defines a tsc step."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

TASK = Path("template/.config/mise/tasks/format").resolve()


def run_task(
    tmp_path: Path, *, has_tsc: bool, usage_all: bool = False, pkl_fails: bool = False
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run the format task with stubbed hk and pkl, returning result and hk args."""
    tools = tmp_path / "bin"
    tools.mkdir()
    calls = tmp_path / "calls"
    calls.touch()
    (tools / "hk").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n')
    (tools / "hk").chmod(0o755)
    answer = "true" if has_tsc else "false"
    pkl = "exit 1" if pkl_fails else f"printf '%s\\n' '{answer}'"
    (tools / "pkl").write_text(f"#!/bin/sh\n{pkl}\n")
    (tools / "pkl").chmod(0o755)
    (tmp_path / "hk.pkl").write_text("// stub\n")
    env = dict(os.environ)
    env.update(PATH=f"{tools}{os.pathsep}{os.environ['PATH']}", CALLS=str(calls))
    if usage_all:
        env["usage_all"] = "true"
    else:
        env.pop("usage_all", None)
    result = subprocess.run(  # noqa: S603
        [TASK], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    return result, calls.read_text().splitlines()


def test_skips_tsc_when_hk_config_defines_it(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, has_tsc=True)

    assert result.returncode == 0, result.stderr
    assert calls == ["fix --no-fail-fast --skip-step tsc"]


def test_omits_skip_step_when_hk_config_has_no_tsc(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, has_tsc=False)

    assert result.returncode == 0, result.stderr
    assert calls == ["fix --no-fail-fast"]


def test_all_flag_passes_all_to_hk_fix(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, has_tsc=True, usage_all=True)

    assert result.returncode == 0, result.stderr
    assert calls == ["fix --no-fail-fast --all --skip-step tsc"]


def test_runs_hk_fix_without_skip_step_when_pkl_fails(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, has_tsc=True, pkl_fails=True)

    assert result.returncode == 0, result.stderr
    assert calls == ["fix --no-fail-fast"]
