"""Check that upgrade keeps the tools in UPGRADE_EXCLUDE, unless tools are named."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "template/.config/mise/tasks/upgrade.jinja"

STUB_MISE = """#!/bin/sh
case "$1" in
  ls) printf 'node  24.1.0  mise.toml  24.1.0\\nuv  0.9.0  mise.toml  0.9.0\\n' ;;
  *) printf '%s\\n' "$*" >> "$CALLS" ;;
esac
"""


def run_task(
    tmp_path: Path, **env: str
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run the task without the Docker option, and return the result and the calls."""
    task = tmp_path / "upgrade"
    task.write_text(TEMPLATE.read_text().replace("[[ docker | lower ]]", "false"))
    task.chmod(0o755)
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "mise").write_text(STUB_MISE)
    (tools / "mise").chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    full = {
        k: v
        for k, v in os.environ.items()
        if k not in {"UPGRADE_EXCLUDE", "usage_tools"}
    }
    full.update(PATH=f"{tools}{os.pathsep}{os.environ['PATH']}", CALLS=str(calls))
    full.update(env)
    result = subprocess.run(  # noqa: S603
        [task], cwd=tmp_path, env=full, capture_output=True, text=True, check=False
    )
    return result, calls.read_text().splitlines()


def test_upgrades_every_tool_without_upgrade_exclude(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path)

    assert result.returncode == 0, result.stderr
    assert calls == ["upgrade --bump --no-global"]


def test_excludes_each_tool_in_upgrade_exclude(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, UPGRADE_EXCLUDE="node uv")

    assert result.returncode == 0, result.stderr
    assert calls == ["upgrade --bump --no-global --exclude node --exclude uv"]


def test_named_tools_override_upgrade_exclude(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, UPGRADE_EXCLUDE="node", usage_tools="node")

    assert result.returncode == 0, result.stderr
    assert calls == ["upgrade --bump --no-global node"]


def test_fails_on_an_excluded_tool_that_no_config_requests(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, UPGRADE_EXCLUDE="nodee")

    assert result.returncode == 2
    assert "UPGRADE_EXCLUDE names nodee" in result.stderr
    assert calls == []


def test_does_not_expand_a_pattern_in_upgrade_exclude(tmp_path: Path) -> None:
    (tmp_path / "node").touch()
    result, calls = run_task(tmp_path, UPGRADE_EXCLUDE="n*")

    assert result.returncode == 2
    assert "UPGRADE_EXCLUDE names n*" in result.stderr
    assert calls == []


def test_treats_a_blank_upgrade_exclude_as_empty(tmp_path: Path) -> None:
    result, calls = run_task(tmp_path, UPGRADE_EXCLUDE="  ")

    assert result.returncode == 0, result.stderr
    assert "keeping" not in result.stdout
    assert calls == ["upgrade --bump --no-global"]
