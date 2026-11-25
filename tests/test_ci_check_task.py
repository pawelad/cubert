"""Check that ci:check skips tasks in CI_CHECK_SKIP, locks uv and sets up a vault."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

TASK = Path("template/.config/mise/tasks/ci/check").resolve()

STUB_MISE = """#!/bin/sh
printf '%s\\n' "$*" >> "$CALLS"
printf '%s %s\\n' "$2" "${UV_LOCKED:-}" >> "$CALLS.uv_locked"
case "$1" in
  tasks) printf 'check\\ncheck:repo\\ncheck:tool\\ncheck:tool:sync\\ntest:python\\n' ;;
esac
case "$*" in
  *" --hidden"*) printf 'check:hidden\\n' ;;
esac
"""

STUB_ANSIBLE = """#!/bin/sh
"""

STUB_UV = """#!/bin/sh
printf 'uv %s\\n' "$*" >> "$CALLS"
exit "${UV_STATUS:-0}"
"""

STUB_ENV = """#!/bin/sh
printf '%s\\n' "$*" >> "$CALLS"
case "$2" in
  install)
    printf '%s\\n' "$ANSIBLE_VAULT_PASSWORD_FILE" > "$CALLS.vault_path"
    cat "$ANSIBLE_VAULT_PASSWORD_FILE" > "$CALLS.vault"
    ;;
esac
"""


def run_task(
    tmp_path: Path, *, ansible: bool = False, uv_lock: bool = False, **env: str
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run the task in `tmp_path` with stubs, and return the result and the calls."""
    tools = tmp_path / "bin"
    tools.mkdir()
    stubs = {"mise": STUB_MISE, "uv": STUB_UV}
    if ansible:
        stubs = {"mise": STUB_ENV, "ansible-playbook": STUB_ANSIBLE}
    if uv_lock:
        (tmp_path / "uv.lock").touch()
    for name, body in stubs.items():
        (tools / name).write_text(body)
        (tools / name).chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    full = {
        k: v
        for k, v in os.environ.items()
        if k not in {"CI", "CI_CHECK_SKIP", "CI_CHECK_SKIP_INSTALL", "UV_LOCKED"}
    }
    full.update(PATH=f"{tools}{os.pathsep}{os.environ['PATH']}", CALLS=str(calls))
    full.update(env)
    full.pop("ANSIBLE_VAULT_PASSWORD_FILE", None)
    result = subprocess.run(  # noqa: S603
        [TASK], cwd=tmp_path, env=full, capture_output=True, text=True, check=False
    )
    return result, calls.read_text().splitlines()


def test_no_skip_list_runs_the_group_tasks(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path)

    assert result.returncode == 0, result.stderr
    assert calls == ["run install", "run check", "run test"]


def test_only_install_gets_uv_locked(tmp_path: Path) -> None:
    result, _ = run_task(tmp_path)

    assert result.returncode == 0, result.stderr
    locked = (tmp_path / "calls.uv_locked").read_text().splitlines()
    assert locked == ["install 1", "check ", "test "]


def test_skip_list_runs_every_other_area_task_hidden_ones_too(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, CI_CHECK_SKIP="check:tool\t\n")

    assert result.returncode == 0, result.stderr
    assert "run check:repo ::: check:hidden" in calls
    assert "run test:python" in calls
    assert not [call for call in calls if "check:tool" in call]


def test_skip_list_with_an_unknown_task_fails(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, CI_CHECK_SKIP="check:typo")

    assert result.returncode == 2
    assert "check:typo" in result.stderr
    assert "run check:repo" not in calls


def test_skip_list_with_a_task_outside_the_groups_fails(tmp_path: Path) -> None:
    result, _ = run_task(tmp_path, CI_CHECK_SKIP="check:tool:sync")

    assert result.returncode == 2
    assert "check:tool:sync" in result.stderr


def test_ci_with_ansible_gets_a_throwaway_vault_password(tmp_path: Path) -> None:
    result, _ = run_task(tmp_path, ansible=True, CI="true")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "calls.vault").read_text().strip()
    assert not Path((tmp_path / "calls.vault_path").read_text().strip()).exists()


def test_skip_install_omits_install_while_running_checks_and_tests(
    tmp_path: Path,
) -> None:
    result, calls = run_task(tmp_path, CI_CHECK_SKIP_INSTALL="1")

    assert result.returncode == 0, result.stderr
    assert calls == ["run check", "run test"]


def test_skip_install_checks_the_uv_lock_before_the_checks(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, uv_lock=True, CI_CHECK_SKIP_INSTALL="1")

    assert result.returncode == 0, result.stderr
    assert calls == ["uv lock --check", "run check", "run test"]


def test_skip_install_with_a_stale_uv_lock_fails_before_the_checks(
    tmp_path: Path,
) -> None:
    result, calls = run_task(
        tmp_path, uv_lock=True, CI_CHECK_SKIP_INSTALL="1", UV_STATUS="1"
    )

    assert result.returncode == 1
    assert calls == ["uv lock --check"]


def test_invalid_skip_install_value_fails(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, CI_CHECK_SKIP_INSTALL="invalid")

    assert result.returncode == 2
    assert "CI_CHECK_SKIP_INSTALL" in result.stderr
    assert calls == []
