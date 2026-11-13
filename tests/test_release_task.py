"""Check the shared release task on a rendered changelog project with a bare origin."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import project_env, render_template, run

TASK = ".config/mise/tasks/release/_default"


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render_template(
        tmp_path_factory.mktemp("render"), changelog="true", openspec="none"
    )


@pytest.fixture
def project(rendered: Path, tmp_path: Path) -> Path:
    """Return a copy of the render with one feature commit, pushed to a bare origin."""
    origin = tmp_path / "origin.git"
    run(
        ["git", "init", "--quiet", "--bare", "--initial-branch=main", str(origin)],
        tmp_path,
    )
    dest = tmp_path / "project"
    shutil.copytree(rendered, dest, symlinks=True)
    git(dest, "init", "--quiet", "--initial-branch=main")
    git(dest, "add", "--all")
    git(dest, "commit", "--quiet", "-m", "chore: render")
    git(dest, "commit", "--quiet", "--allow-empty", "-m", "feat: add the first feature")
    git(dest, "remote", "add", "origin", str(origin))
    git(dest, "push", "--quiet", "origin", "main")
    return dest


def git(cwd: Path, *args: str) -> str:
    command = [
        "git",
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@example.com",
        *args,
    ]
    return run(command, cwd).strip()


def release(
    project: Path, version: str, *, push: bool = False, ci: str = "passed"
) -> subprocess.CompletedProcess[str]:
    tools = project.parent / "bin"
    tools.mkdir(exist_ok=True)
    gh = tools / "gh"
    # The stub answers `gh run list` with one push run in the given state.
    gh.write_text(f'#!/bin/sh\necho "$*" >> "{project.parent}/gh-calls"\necho {ci}\n')
    gh.chmod(0o755)
    env = project_env()
    env.update(
        PATH=f"{tools}{os.pathsep}{env['PATH']}",
        usage_version=version,
        usage_no_push="false" if push else "true",
        GIT_AUTHOR_NAME="test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    return subprocess.run(  # noqa: S603
        ["bash", TASK],  # noqa: S607
        cwd=project,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )


def test_first_release_writes_the_section_commits_and_tags(project: Path) -> None:
    result = release(project, "v0.1.0")

    assert result.returncode == 0, result.stderr
    changelog = (project / "CHANGELOG.md").read_text()
    assert changelog.count("# Changelog") == 1
    assert "## [0.1.0] - " in changelog
    assert "- Add the first feature (" in changelog
    assert git(project, "log", "-1", "--format=%s") == "chore(release): v0.1.0"
    message = git(project, "tag", "--list", "v0.1.0", "--format=%(contents)")
    assert message.startswith("### Features")
    assert "Add the first feature" in message
    assert not (project.parent / "gh-calls").exists()


def test_second_release_keeps_one_header_and_lists_only_new_commits(
    project: Path,
) -> None:
    assert release(project, "0.1.0").returncode == 0
    git(
        project,
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        "fix: repair the second thing",
    )
    git(project, "push", "--quiet", "origin", "main")

    result = release(project, "0.2.0")

    assert result.returncode == 0, result.stderr
    changelog = (project / "CHANGELOG.md").read_text()
    assert changelog.count("# Changelog") == 1
    assert changelog.index("## [0.2.0]") < changelog.index("## [0.1.0]")
    message = git(project, "tag", "--list", "v0.2.0", "--format=%(contents)")
    assert "Repair the second thing" in message
    assert "Add the first feature" not in message


@pytest.mark.parametrize(
    ("setup", "version", "error"),
    [
        (None, "1.2", "use a version such as 1.2.0"),
        ("dirty", "0.1.0", "commit or stash"),
        ("unpushed", "0.1.0", "HEAD must equal origin/main"),
        ("tagged", "0.1.0", "v0.1.0 already exists"),
        ("tagged", "0.0.9", "v0.0.9 is not newer than v0.1.0"),
    ],
)
def test_refuses_an_unsafe_release(
    project: Path, setup: str | None, version: str, error: str
) -> None:
    if setup == "dirty":
        (project / "notes.txt").write_text("draft\n")
    elif setup == "unpushed":
        git(project, "commit", "--quiet", "--allow-empty", "-m", "feat: not pushed")
    elif setup == "tagged":
        git(project, "tag", "v0.1.0")
        git(project, "push", "--quiet", "origin", "v0.1.0")
    head = git(project, "rev-parse", "HEAD")

    result = release(project, version)

    assert result.returncode == 1
    assert error in result.stderr
    assert git(project, "rev-parse", "HEAD") == head


@pytest.mark.parametrize("ci", ["failed", "running", "missing"])
def test_push_requires_passing_ci_before_it_changes_anything(
    project: Path, ci: str
) -> None:
    head = git(project, "rev-parse", "HEAD")

    result = release(project, "0.1.0", push=True, ci=ci)

    assert result.returncode == 1
    assert f"CI on HEAD is {ci}" in result.stderr
    assert git(project, "rev-parse", "HEAD") == head
    assert git(project, "tag", "--list") == ""


def test_push_without_a_terminal_stays_local(project: Path) -> None:
    result = release(project, "0.1.0", push=True, ci="passed")

    assert result.returncode == 0, result.stderr
    assert "v0.1.0 stays local" in result.stdout
    assert git(project, "ls-remote", "--tags", "origin") == ""
    assert "run list" in (project.parent / "gh-calls").read_text()
