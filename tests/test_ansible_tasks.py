"""Check Ansible playbook discovery and template-only hook changes."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.support import project_env, render_template, run


@pytest.fixture
def ansible_project(tmp_path: Path) -> tuple[Path, dict[str, dict[str, Any]]]:
    project = render_template(tmp_path, ansible="true", openspec="none")
    steps = json.loads(
        run(
            ["pkl", "eval", "--format", "json", ".config/hk/cubert.pkl"],
            project,
        )
    )["steps"]
    return project, steps


def test_syntax_check_visits_nested_playbooks_and_reports_failures(
    tmp_path: Path, ansible_project: tuple[Path, dict[str, dict[str, Any]]]
) -> None:
    project, steps = ansible_project
    playbooks = project / "ansible/playbooks"
    (playbooks / "nested dir").mkdir(parents=True)
    for name in ["nested dir/bad.yaml", "nested dir/good.yml", "root.yml"]:
        (playbooks / name).write_text("---\n")
    for directory in [
        "tasks",
        "handlers",
        "vars",
        "group_vars",
        "host_vars",
        "roles",
        "templates",
        "files",
    ]:
        fragment = playbooks / "nested dir" / directory / "fragment.yml"
        fragment.parent.mkdir(parents=True)
        fragment.write_text("not a playbook\n")
    tools = tmp_path / "bin"
    tools.mkdir()
    executable = tools / "ansible-playbook"
    executable.write_text(
        '#!/bin/sh\nshift\nprintf "%s\\n" "$@" >> "$ANSIBLE_CALLS"\n'
        'for f do case "$f" in *bad.yaml) exit 7 ;; esac; done\n'
    )
    executable.chmod(0o755)
    calls = tmp_path / "ansible-calls"
    env = project_env()
    env.update(PATH=f"{tools}{os.pathsep}{env['PATH']}", ANSIBLE_CALLS=str(calls))
    command = steps["ansible-syntax-check"]["check"]

    result = subprocess.run(  # noqa: S603
        ["bash", "-c", command],  # noqa: S607
        cwd=project / "ansible",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, result.stderr
    assert sorted(calls.read_text().splitlines()) == [
        "playbooks/nested dir/bad.yaml",
        "playbooks/nested dir/good.yml",
        "playbooks/root.yml",
    ]


@pytest.mark.parametrize(
    "directory", ["roles/demo", "collections/ansible_collections/demo/util/roles/demo"]
)
def test_template_only_change_triggers_ansible_step(
    tmp_path: Path,
    ansible_project: tuple[Path, dict[str, dict[str, Any]]],
    directory: str,
) -> None:
    project, _ = ansible_project
    run(["git", "init", "--quiet"], project)
    template = project / "ansible" / directory / "templates/config.j2"
    template.parent.mkdir(parents=True)
    template.write_text("hello\n")
    run(["git", "add", "--force", str(template)], project)
    run(["git", "add", "--all"], project)
    tools = tmp_path / "bin"
    tools.mkdir()
    for tool in ["ansible-lint", "ansible-playbook"]:
        executable = tools / tool
        executable.write_text('#!/bin/sh\necho invoked >> "$ANSIBLE_CALLS"\nexit 7\n')
        executable.chmod(0o755)
    playbook = project / "ansible/playbooks/site.yml"
    playbook.parent.mkdir(parents=True)
    playbook.write_text("---\n")
    run(["git", "add", "--all"], project)
    run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "commit",
            "--quiet",
            "--no-verify",
            "-m",
            "chore: fixture",
        ],
        project,
    )
    template.write_text("changed\n")
    run(["git", "add", "--force", str(template)], project)
    env = project_env()
    env.pop("HK", None)
    calls = tmp_path / "ansible-calls"
    env.update(
        PATH=f"{tools}{os.pathsep}{env['PATH']}", ANSIBLE_CALLS=str(calls), HK_MISE="0"
    )

    result = subprocess.run(
        ["hk", "run", "pre-commit", "--check", "--step", "ansible-template"],  # noqa: S607
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert calls.exists(), result.stdout + result.stderr
    assert calls.read_text().strip() == "invoked"
