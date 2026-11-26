"""Find file tasks that mise skips because another task directory has the name."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support import load_script

check_task_names = load_script("template/.config/hk/checks/check_task_names.py")


def task(root: Path, path: str, executable: bool = True) -> None:
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("#!/usr/bin/env bash\n")
    file.chmod(0o755 if executable else 0o644)


@pytest.mark.parametrize(
    ("relative", "name"),
    [
        ("install", "install"),
        ("ansible/install", "ansible:install"),
        ("ansible/install.sh", "ansible:install"),
        ("check/_default", "check"),
    ],
)
def test_task_name_follows_mise(relative: str, name: str) -> None:
    assert check_task_names.task_name(Path(relative)) == name


def test_project_file_with_a_shared_name_fails(tmp_path: Path) -> None:
    task(tmp_path, ".config/mise/tasks/ansible/install")
    task(tmp_path, "mise-tasks/ansible/install")
    expected = (
        "mise-tasks/ansible/install: mise runs .config/mise/tasks/ansible/install"
        " for ansible:install, not this file"
    )
    assert check_task_names.failures(tmp_path) == [expected]


def test_default_file_and_plain_file_share_a_name(tmp_path: Path) -> None:
    task(tmp_path, ".config/mise/tasks/check/_default")
    task(tmp_path, "mise-tasks/check")
    assert check_task_names.failures(tmp_path)


def test_mise_tasks_dir_wins_over_the_shared_dir(tmp_path: Path) -> None:
    task(tmp_path, ".config/mise/tasks/setup")
    task(tmp_path, "mise/tasks/setup")
    [failure] = check_task_names.failures(tmp_path)
    assert failure.startswith(".config/mise/tasks/setup: mise runs mise/tasks/setup")


def test_distinct_names_pass(tmp_path: Path) -> None:
    task(tmp_path, ".config/mise/tasks/ansible/install")
    task(tmp_path, "mise-tasks/ansible/deploy")
    assert check_task_names.failures(tmp_path) == []


@pytest.mark.parametrize(
    ("shared", "project"),
    [
        ("install", "mise-tasks/.install"),
        ("ansible/install", "mise-tasks/.ansible/install"),
    ],
)
def test_hidden_files_are_not_tasks(tmp_path: Path, shared: str, project: str) -> None:
    task(tmp_path, f".config/mise/tasks/{shared}")
    task(tmp_path, project)
    assert check_task_names.failures(tmp_path) == []


def test_non_executable_file_is_not_a_task(tmp_path: Path) -> None:
    task(tmp_path, ".config/mise/tasks/install")
    task(tmp_path, "mise-tasks/install", executable=False)
    assert check_task_names.failures(tmp_path) == []


def test_symlinked_shared_dir_is_followed(tmp_path: Path) -> None:
    task(tmp_path, "template/tasks/ansible/install")
    (tmp_path / ".config/mise/tasks").mkdir(parents=True)
    (tmp_path / ".config/mise/tasks/ansible").symlink_to(
        tmp_path / "template/tasks/ansible"
    )
    task(tmp_path, "mise-tasks/ansible/install")
    assert check_task_names.failures(tmp_path)


def test_main_prints_the_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    task(tmp_path, ".config/mise/tasks/install")
    task(tmp_path, "mise-tasks/install")
    monkeypatch.chdir(tmp_path)
    assert check_task_names.main() == 1
    assert '[tasks."<name>"] with its own run to mise.toml' in capsys.readouterr().out
