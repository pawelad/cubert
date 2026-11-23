"""Check dependency audits for default projects and adopted backends."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from tests.support import project_env, render_template, run

LOCKS = [
    ".mise/locks/pypi-copier/tool/uv.lock",
    "apps/backend/uv.lock",
    "apps/web/bun.lock",
    "skills/demo/hello/scripts/hello.py.lock",
]


def audit_deps(
    tmp_path: Path, *, scanner_status: int = 0, exclude: str | None = None
) -> tuple[Path, subprocess.CompletedProcess[str], list[str]]:
    """Run audit:deps on a project with `LOCKS`, and return the scanner's arguments."""
    project = render_template(tmp_path, openspec="none")
    run(["git", "init", "--quiet"], project)
    for name in LOCKS:
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
    calls.touch()
    env = project_env()
    env.update(
        PATH=f"{tools}{os.pathsep}{env['PATH']}",
        SCANNER_CALLS=str(calls),
        SCANNER_STATUS=str(scanner_status),
    )
    if exclude is not None:
        env["AUDIT_DEPS_EXCLUDE"] = exclude

    result = subprocess.run(
        ["bash", ".config/mise/tasks/audit/deps"],  # noqa: S607
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return project, result, calls.read_text().splitlines()


@pytest.mark.parametrize("scanner_status", [0, 7])
def test_default_project_scans_tool_and_nested_application_lockfiles(
    tmp_path: Path, scanner_status: int
) -> None:
    project, result, arguments = audit_deps(tmp_path, scanner_status=scanner_status)

    config = tomllib.loads((project / "mise.toml").read_text())
    assert "osv-scanner" in config["tools"]
    required = (project / ".config/mise/required-tools").read_text().splitlines()
    assert "osv-scanner" in required
    assert result.returncode == scanner_status, result.stderr
    assert arguments[:2] == ["scan", "source"]
    assert arguments[2::2] == ["--lockfile"] * len(LOCKS)
    expected = [f"uv.lock:{n}" if n.endswith(".py.lock") else n for n in LOCKS]
    assert sorted(arguments[3::2]) == sorted(expected)


@pytest.mark.parametrize(
    "exclude",
    ["apps/*/uv.lock apps/web/*", "\n  apps/*/uv.lock\n  apps/web/*\n"],
)
def test_audit_deps_skips_the_locks_that_audit_deps_exclude_matches(
    tmp_path: Path, exclude: str
) -> None:
    _, result, arguments = audit_deps(tmp_path, exclude=exclude)

    assert result.returncode == 0, result.stderr
    assert sorted(arguments[3::2]) == [
        ".mise/locks/pypi-copier/tool/uv.lock",
        "uv.lock:skills/demo/hello/scripts/hello.py.lock",
    ]


def test_audit_deps_exclude_pattern_that_matches_no_lock_fails(
    tmp_path: Path,
) -> None:
    _, result, arguments = audit_deps(tmp_path, exclude="apps/backnd/uv.lock")

    assert result.returncode == 2
    assert "apps/backnd/uv.lock, which matches no lock" in result.stderr
    assert arguments == []
