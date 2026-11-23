"""Check that a plain `git worktree add` runs worktree:setup through post-checkout.

The test renders a project, installs its post-checkout hook and adds a worktree with
git alone, as Superset, Jean, herdr and Orca do. It does not use worktrunk's hooks.
"""

from __future__ import annotations

import os
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.support import ROOT, project_env, run, snapshot_template

MARKER = "cubert-worktree-setup-done"
NEEDED_TOOLS = ("git", "mise", "copier", "wt")
AGENT_DIRS = ("tmp", ".claude", ".codex", ".pi")

pytestmark = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in NEEDED_TOOLS),
    reason=f"needs {', '.join(NEEDED_TOOLS)} on PATH",
)


@dataclass
class Project:
    primary: Path
    worktree: Path
    env: dict[str, str]
    hook_output: str

    def git(self, *args: str, cwd: Path | None = None) -> str:
        return run(["git", *args], cwd or self.worktree, self.env)


def make_env(base: Path) -> dict[str, str]:
    env = project_env()
    env.update(
        {
            # No global hooks or identity: only the project's own hook may run.
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            # The worktree is a new path, so mise would ask to trust it.
            "MISE_TRUSTED_CONFIG_PATHS": str(base),
        }
    )
    return env


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Project:
    base = tmp_path_factory.mktemp("worktree").resolve()
    env = make_env(base)
    primary = base / "demo"
    worktree = base / "demo-feature"
    source = base / "cubert"
    ref = snapshot_template(source)
    run(
        [
            "copier",
            "copy",
            "--quiet",
            "--defaults",
            "--vcs-ref",
            ref,
            "-d",
            "project_name=demo",
            "-d",
            "description=A demo project.",
            "-d",
            "opentofu=true",
            "-d",
            "opentofu_dir=src/opentofu",
            "-d",
            "ansible=true",
            "-d",
            "ansible_dir=src/ansible",
            "-d",
            "openspec_changes_tracked=false",
            str(source),
            str(primary),
        ],
        base,
        env,
    )
    # Only worktrunk, which cubert already installed: the hook calls `wt`, and CI has no
    # `wt` outside mise.
    worktrunk = tomllib.loads((ROOT / "mise.toml").read_text())["tools"]["worktrunk"]
    (primary / "mise.toml").write_text(f'[tools]\nworktrunk = "{worktrunk}"\n')
    links = primary / ".worktreelinks"
    links.write_text(f"{links.read_text()}secrets/token\n")
    run(["git", "init", "--quiet", "--initial-branch", "main"], primary, env)
    run(["git", "add", "--all"], primary, env)
    commit = ["git", "commit", "--quiet", "--no-verify", "-m", "chore: render"]
    run(commit, primary, env)

    # Untracked files that only the primary checkout has.
    (primary / ".env").write_text("DEMO=1\n")
    (primary / "src/opentofu/.env").write_text("TOFU=1\n")
    (primary / "src/ansible/.vault_pass").write_text("vault\n")
    for name in AGENT_DIRS:
        (primary / name).mkdir()
    (primary / "secrets").mkdir()
    (primary / "secrets/token").write_text("secret\n")

    hooks = primary / ".git/hooks"
    hooks.mkdir(exist_ok=True)
    shutil.copy(primary / ".config/git/post-checkout", hooks / "post-checkout")
    (hooks / "post-checkout").chmod(0o755)

    add = ["git", "worktree", "add", "-b", "feature", str(worktree)]
    output = run(add, primary, env)
    return Project(primary, worktree, env, output)


def test_hook_runs_worktree_setup(project: Project) -> None:
    git_dir = Path(project.git("rev-parse", "--absolute-git-dir").strip())
    assert (git_dir / MARKER).is_file(), project.hook_output


@pytest.mark.parametrize("name", AGENT_DIRS)
def test_agent_dirs_link_to_primary(project: Project, name: str) -> None:
    link = project.worktree / name
    assert link.is_symlink()
    assert link.resolve() == (project.primary / name).resolve()


def test_agent_dir_missing_in_primary_is_not_linked(project: Project) -> None:
    assert not (project.worktree / ".gemini").exists()


@pytest.mark.parametrize(
    "path",
    ["src/opentofu/.env", "src/ansible/.vault_pass", "secrets/token"],
)
def test_worktreelinks_path_links_to_primary(project: Project, path: str) -> None:
    link = project.worktree / path
    assert link.is_symlink()
    assert link.resolve() == (project.primary / path).resolve()


def test_worktreelinks_dir_missing_in_primary_is_created_and_linked(
    project: Project,
) -> None:
    link = project.worktree / "openspec/changes"
    assert link.is_symlink()
    assert link.resolve() == (project.primary / "openspec/changes").resolve()
    assert (project.primary / "openspec/changes").is_dir()


def test_worktreeinclude_file_is_copied(project: Project) -> None:
    copy = project.worktree / ".env"
    assert copy.is_file()
    assert not copy.is_symlink()
    assert copy.read_text() == "DEMO=1\n"


def test_second_checkout_does_nothing(project: Project) -> None:
    (project.primary / ".gemini").mkdir()
    (project.worktree / ".env").unlink()
    git_dir = Path(project.git("rev-parse", "--absolute-git-dir").strip())
    marker_time = (git_dir / MARKER).stat().st_mtime_ns

    project.git("checkout", "--quiet", "--detach")
    project.git("checkout", "--quiet", "feature")

    assert not (project.worktree / ".gemini").exists()
    assert not (project.worktree / ".env").exists()
    assert (git_dir / MARKER).stat().st_mtime_ns == marker_time
