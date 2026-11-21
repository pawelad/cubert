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

    assert (project / directory).is_dir()
    if feature == "opentofu":
        init = (project / ".config/mise/tasks/opentofu/init").read_text()
        assert f'#MISE dir="{directory}"' in init.splitlines()
    else:
        config = tomllib.loads((project / "mise.toml").read_text())
        assert config["tasks"]["ansible:install"]["dir"] == directory


def test_description_with_quotes_renders_valid_pyproject(tmp_path: Path) -> None:
    project = render_template(tmp_path, python="true", description=TRICKY)

    parsed = tomllib.loads((project / "pyproject.toml").read_text())

    assert parsed["project"]["description"] == TRICKY


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
