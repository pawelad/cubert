"""Check that answers with quotes and backslashes render into valid files."""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from tests.support import project_env, render_template, run

pytestmark = pytest.mark.skipif(
    shutil.which("copier") is None, reason="needs copier on PATH"
)

TRICKY = 'A "quoted" project with a \\ backslash.'


@pytest.mark.parametrize(
    ("feature", "question"), [("opentofu", "opentofu_dir"), ("ansible", "ansible_dir")]
)
@pytest.mark.parametrize(
    "directory",
    [
        "",
        "../outside",
        "/absolute",
        "my infra",
        'infra/"quoted"',
        "-rf",
        "./-rf",
        "././-rf",
        ".//-rf",
        "././/-rf",
        ".",
        "./infra",
        "infra/",
        "infra//tofu",
        "infra/./tofu",
    ],
)
def test_unsupported_feature_directory_fails_before_render(
    tmp_path: Path, feature: str, question: str, directory: str
) -> None:
    with pytest.raises(AssertionError, match="Validation error for question"):
        render_template(tmp_path, **{feature: "true", question: directory})


@pytest.mark.parametrize("feature", ["opentofu", "ansible"])
@pytest.mark.parametrize("directory", ["src/infra-tools", "apps/-x"])
def test_nested_feature_directory_is_used_by_its_install_task(
    tmp_path: Path, feature: str, directory: str
) -> None:
    question = "opentofu_dir" if feature == "opentofu" else "ansible_dir"
    project = render_template(tmp_path, **{feature: "true", question: directory})

    if feature == "opentofu":
        assert (project / directory).is_dir()
        init = (project / ".config/mise/tasks/opentofu/init").read_text()
        assert f'#MISE dir="{directory}"' in init.splitlines()
    else:
        install = (project / ".config/mise/tasks/ansible/install").read_text()
        assert f'dir="{directory}"' in install.splitlines()


# A new project has no Ansible directory until its first playbook.
def test_ansible_install_passes_without_the_ansible_directory(tmp_path: Path) -> None:
    project = render_template(tmp_path, ansible="true")

    assert not (project / "ansible").exists()
    run([".config/mise/tasks/ansible/install"], project)


def test_description_with_quotes_renders_valid_pyproject(tmp_path: Path) -> None:
    project = render_template(tmp_path, python="true", description=TRICKY)

    parsed = tomllib.loads((project / "pyproject.toml").read_text())

    assert parsed["project"]["description"] == TRICKY


def test_long_description_wraps_in_openspec_config_within_yamllint_limit(
    tmp_path: Path,
) -> None:
    description = " ".join(["A long description that keeps going."] * 6)
    project = render_template(tmp_path, description=description)
    lines = (project / "openspec/config.yaml").read_text().splitlines()

    assert all(len(line) <= 88 for line in lines)
    start = lines.index("context: |") + 1
    context = " ".join(line.strip() for line in lines[start : start + 3])
    assert context.startswith(f"`demo`: {description}")


# worktree:setup links openspec/changes into a worktree, and git must ignore the link.
def test_untracked_openspec_changes_stay_out_of_git_as_a_dir_or_a_link(
    tmp_path: Path,
) -> None:
    project = render_template(tmp_path, openspec_changes_tracked="false")
    run(["git", "init", "--quiet"], project)

    assert "openspec/changes/" in (project / ".worktreelinks").read_text().splitlines()
    assert not (project / "openspec/changes/.gitkeep").exists()
    (project / "openspec/changes/demo").mkdir(parents=True)
    (project / "openspec/changes/demo/proposal.md").write_text("# Demo\n")
    status = ["git", "status", "--porcelain", "-uall", "openspec/changes"]
    assert run(status, project) == ""
    shutil.move(project / "openspec/changes", tmp_path / "changes")
    (project / "openspec/changes").symlink_to(tmp_path / "changes")
    assert run(status, project) == ""


@pytest.mark.parametrize("body", ["echo mine", "mise run worktree:setup"])
def test_hooks_install_keeps_a_post_checkout_hook_that_is_not_cubert(
    tmp_path: Path,
    body: str,
) -> None:
    project = render_template(tmp_path)
    run(["git", "init", "--quiet", "--initial-branch", "main"], project)
    foreign = project / ".git/hooks/post-checkout"
    content = f"#!/bin/sh\n{body}\n"
    foreign.write_text(content)

    run(["bash", ".config/mise/tasks/hooks/install"], project)

    assert foreign.read_text() == content
    ours = foreign.parent / "post-checkout.cubert"
    assert "mise run worktree:setup" in ours.read_text()


def test_hooks_install_replace_moves_a_project_hook_to_a_backup(
    tmp_path: Path,
) -> None:
    project = render_template(tmp_path)
    run(["git", "init", "--quiet", "--initial-branch", "main"], project)
    hooks = project / ".git/hooks"
    (hooks / "post-checkout").write_text("#!/bin/sh\nmise run worktree:setup\n")
    run(["bash", ".config/mise/tasks/hooks/install"], project)
    env = project_env()
    env["usage_replace"] = "true"

    run(["bash", ".config/mise/tasks/hooks/install"], project, env)

    assert "mise run worktree:setup" in (hooks / "post-checkout.bak").read_text()
    assert "Template-owned" in (hooks / "post-checkout").read_text()
    assert not (hooks / "post-checkout.cubert").exists()


def test_hooks_install_replace_keeps_an_earlier_backup(tmp_path: Path) -> None:
    project = render_template(tmp_path)
    run(["git", "init", "--quiet", "--initial-branch", "main"], project)
    hooks = project / ".git/hooks"
    (hooks / "post-checkout").write_text("#!/bin/sh\necho new\n")
    (hooks / "post-checkout.bak").write_text("#!/bin/sh\necho old\n")
    env = project_env()
    env["usage_replace"] = "true"

    command = ["bash", ".config/mise/tasks/hooks/install"]
    result = subprocess.run(  # noqa: S603
        command, cwd=project, env=env, capture_output=True, text=True, check=False
    )

    assert result.returncode != 0
    assert "post-checkout.bak exists" in result.stderr
    assert (hooks / "post-checkout.bak").read_text() == "#!/bin/sh\necho old\n"
    assert (hooks / "post-checkout").read_text() == "#!/bin/sh\necho new\n"


def test_hooks_install_replaces_its_own_post_checkout_hook(tmp_path: Path) -> None:
    project = render_template(tmp_path)
    run(["git", "init", "--quiet", "--initial-branch", "main"], project)

    run(["bash", ".config/mise/tasks/hooks/install"], project)
    run(["bash", ".config/mise/tasks/hooks/install"], project)

    hooks = project / ".git/hooks"
    assert "mise run worktree:setup" in (hooks / "post-checkout").read_text()
    assert not (hooks / "post-checkout.cubert").exists()


@pytest.mark.parametrize("delegation", ["", "exec "])
def test_chained_post_checkout_hook_passes_repo_guard(
    tmp_path: Path, delegation: str
) -> None:
    project = render_template(tmp_path)
    run(["git", "init", "--quiet", "--initial-branch", "main"], project)
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "hk").write_text("#!/bin/sh\nexit 0\n")
    (tools / "hk").chmod(0o755)
    env = project_env()
    env.pop("CI", None)
    env["PATH"] = f"{tools}{os.pathsep}{env['PATH']}"
    (project / "mise.lock").write_text("lockfile_version = 3\n")
    hook = project / ".git/hooks/post-checkout"
    hook.write_text("#!/bin/sh\necho mine\n")
    hook.chmod(0o755)
    run(["bash", ".config/mise/tasks/hooks/install"], project, env)
    with hook.open("a") as file:
        file.write(f'{delegation}"{hook}.cubert" "$@"\n')

    run(["bash", ".config/mise/tasks/check/repo"], project, env)

    # A chain must not hide a stale delegated copy after a template update.
    Path(f"{hook}.cubert").write_text("#!/bin/sh\nexit 0\n")
    result = subprocess.run(
        ["bash", ".config/mise/tasks/check/repo"],  # noqa: S607
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "post-checkout worktree hook is missing or out of date" in result.stderr
