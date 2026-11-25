"""Check the shared release task on a rendered changelog project with a bare origin."""

from __future__ import annotations

import os
import pty
import re
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


def add_hooks(project: Path, **runs: str) -> None:
    """Define each `release:<name>` hook task, with `version.txt` tracked and pushed."""
    usage = {"bump": 'arg "<version>"', "publish": 'arg "<tag>"'}
    config = project / "mise.toml"
    for name, command in runs.items():
        config.write_text(
            f'{config.read_text()}\n[tasks."release:{name}"]\n'
            f"usage = '{usage[name]}'\nrun = '{command}'\n"
        )
    (project / "version.txt").write_text("0.0.0\n")
    git(project, "add", "--all")
    git(project, "commit", "--quiet", "-m", "chore: add release hooks")
    git(project, "push", "--quiet", "origin", "main")


def release(
    project: Path,
    version: str,
    *,
    push: bool = False,
    ci: str = "passed",
    confirm: str | bool | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run release with stubbed `gh` and `gum`.

    `confirm` supplies a `read` line when a string, or stubs `gum confirm` when a bool.
    """
    tools = project.parent / "bin"
    tools.mkdir(exist_ok=True)
    gh = tools / "gh"
    # The stub answers `gh run list` with one push run in the given state.
    gh.write_text(f'#!/bin/sh\necho "$*" >> "{project.parent}/gh-calls"\necho {ci}\n')
    gh.chmod(0o755)
    gum_bin = tools / "gum"
    if isinstance(confirm, bool):
        status = 0 if confirm else 1
        gum_bin.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "--version" ]; then echo "gum 2.0.2"; exit 0; fi\n'
            f'echo "$*" >> "{project.parent}/gum-calls"\n'
            f"exit {status}\n"
        )
    else:
        gum_bin.write_text("#!/bin/sh\nexit 1\n")
    gum_bin.chmod(0o755)
    env = project_env()
    env.update(
        PATH=f"{tools}{os.pathsep}{env['PATH']}",
        usage_version=version,
        usage_no_push="false" if push else "true",
        GIT_AUTHOR_NAME="test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="test",
        GIT_COMMITTER_EMAIL="test@example.com",
        # The task lists the project tasks, and mise asks to trust a new path.
        MISE_TRUSTED_CONFIG_PATHS=str(project.parent),
        # A hook run would lock and install the render's unpinned tools.
        MISE_LOCKFILE="false",
        MISE_AUTO_INSTALL="false",
    )
    if confirm is None:
        return subprocess.run(  # noqa: S603
            ["bash", TASK],  # noqa: S607
            cwd=project,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
    # The task asks only on a terminal, so a pty answers its prompt.
    main, terminal = pty.openpty()
    if isinstance(confirm, str):
        os.write(main, f"{confirm}\n".encode())
    try:
        return subprocess.run(  # noqa: S603
            ["bash", TASK],  # noqa: S607
            cwd=project,
            env=env,
            stdin=terminal,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        os.close(terminal)
        os.close(main)


def test_first_release_is_an_initial_release_section_commit_and_tag(
    project: Path,
) -> None:
    result = release(project, "v0.1.0")

    assert result.returncode == 0, result.stderr
    changelog = (project / "CHANGELOG.md").read_text()
    assert changelog.count("# Changelog") == 1
    section = (
        r"by hand\.\n\n## \[0\.1\.0\] - \d{4}-\d{2}-\d{2}\n\nInitial release\.\n\Z"
    )
    assert re.search(section, changelog)
    assert "Add the first feature" not in changelog
    assert git(project, "log", "-1", "--format=%s") == "chore(release): v0.1.0"
    message = git(project, "tag", "--list", "v0.1.0", "--format=%(contents)")
    assert message.strip() == "Initial release."
    assert not (project.parent / "gh-calls").exists()


def test_second_release_tags_with_its_section_on_unwrapped_lines(
    project: Path,
) -> None:
    assert release(project, "0.1.0").returncode == 0
    git(project, "commit", "--quiet", "--allow-empty", "-m", "fix: repair a thing")
    commit = git(project, "rev-parse", "HEAD")
    git(project, "commit", "--quiet", "--allow-empty", "-m", "feat: add a PR (#7)")
    git(project, "push", "--quiet", "origin", "main")

    result = release(project, "0.2.0")

    assert result.returncode == 0, result.stderr
    changelog = (project / "CHANGELOG.md").read_text()
    assert changelog.count("# Changelog") == 1
    assert changelog.index("## [0.2.0]") < changelog.index("## [0.1.0]")
    message = git(project, "tag", "--list", "v0.2.0", "--format=%(contents)")
    assert message.startswith("### Features")
    repo = "https://github.com/pawelad/demo"
    assert f"- Add a PR ([#7]({repo}/pull/7))" in message
    # CHANGELOG.md wraps the long link, but GitHub would render that break.
    assert f"- Repair a thing\n  ([{commit[:7]}]" in changelog
    assert f"- Repair a thing ([{commit[:7]}]({repo}/commit/{commit}))" in message
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


def test_bump_hook_gets_the_bare_version_and_shares_the_release_commit(
    project: Path,
) -> None:
    add_hooks(project, bump='echo "$usage_version" > version.txt')

    result = release(project, "v0.1.0")

    assert result.returncode == 0, result.stderr
    assert (project / "version.txt").read_text() == "0.1.0\n"
    files = git(project, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert sorted(files) == ["CHANGELOG.md", "version.txt"]
    assert git(project, "status", "--porcelain") == ""


def test_bump_hook_that_creates_an_untracked_file_stops_the_release(
    project: Path,
) -> None:
    add_hooks(project, bump="touch new-version-file")
    head = git(project, "rev-parse", "HEAD")

    result = release(project, "0.1.0")

    assert result.returncode == 1
    assert "release:bump created untracked files" in result.stderr
    assert "new-version-file" in result.stderr
    assert git(project, "rev-parse", "HEAD") == head
    assert git(project, "tag", "--list") == ""


def test_failing_bump_hook_stops_the_release(project: Path) -> None:
    add_hooks(project, bump="exit 3")
    head = git(project, "rev-parse", "HEAD")

    result = release(project, "0.1.0")

    assert result.returncode == 1
    assert "release:bump failed" in result.stderr
    assert git(project, "rev-parse", "HEAD") == head


@pytest.mark.parametrize("hooks", [False, True])
def test_confirmed_push_publishes_with_the_hook_in_place_of_the_github_release(
    project: Path, hooks: bool
) -> None:
    if hooks:
        add_hooks(project, publish='echo "$usage_tag" > ../published')

    result = release(project, "0.1.0", push=True, confirm="y")

    assert result.returncode == 0, result.stderr
    assert "v0.1.0" in git(project, "ls-remote", "--tags", "origin")
    calls = (project.parent / "gh-calls").read_text()
    assert ("release create v0.1.0 --title v0.1.0" in calls) != hooks
    published = project.parent / "published"
    assert published.exists() == hooks
    if hooks:
        assert published.read_text() == "v0.1.0\n"


@pytest.mark.parametrize(
    ("answer", "pushed"), [("Y", True), ("yes", True), ("n", False)]
)
def test_prompt_accepts_y_or_yes_in_any_case(
    project: Path, answer: str, pushed: bool
) -> None:
    result = release(project, "0.1.0", push=True, confirm=answer)

    assert result.returncode == 0, result.stderr
    assert ("v0.1.0" in git(project, "ls-remote", "--tags", "origin")) == pushed


@pytest.mark.parametrize("accepted", [True, False])
def test_gum_confirms_the_push_when_installed(project: Path, accepted: bool) -> None:
    result = release(project, "0.1.0", push=True, confirm=accepted)

    assert result.returncode == 0, result.stderr
    assert (
        "confirm --default=false Push main and v0.1.0, then run:"
        in (project.parent / "gum-calls").read_text()
    )
    assert ("v0.1.0" in git(project, "ls-remote", "--tags", "origin")) == accepted


@pytest.mark.parametrize("hooks", [False, True])
def test_local_release_names_the_publish_step_that_a_push_would_run(
    project: Path, hooks: bool
) -> None:
    if hooks:
        add_hooks(project, publish='echo "$usage_tag" > ../published')

    result = release(project, "0.1.0")

    assert result.returncode == 0, result.stderr
    assert ("mise run release:publish v0.1.0" in result.stdout) == hooks
    assert ("gh release create v0.1.0 --title v0.1.0" in result.stdout) != hooks
    assert not (project.parent / "published").exists()


def test_failing_publish_hook_names_the_retry(project: Path) -> None:
    add_hooks(project, publish="exit 3")

    result = release(project, "0.1.0", push=True, confirm="y")

    assert result.returncode == 1
    assert "pushed v0.1.0, but release:publish failed" in result.stderr
    assert "Retry: mise run release:publish v0.1.0" in result.stderr
    assert "v0.1.0" in git(project, "ls-remote", "--tags", "origin")
