"""Check the operator credential wiring that each `secrets_provider` answer renders."""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from tests.support import project_env, render_template

RECIPIENT = "age12qrxf73pllq0kn0rjz07auqsc4jm0h5357eh2v4y4v8hpgdqdu9szdjrx8"
ANSWERS = {
    "none": {},
    "proton-pass": {"secrets_vault": "demo-vault"},
    "age": {"secrets_age_recipient": RECIPIENT},
}


@pytest.fixture(scope="module", params=list(ANSWERS))
def project(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> tuple[str, Path]:
    if shutil.which("copier") is None:
        pytest.skip("needs copier on PATH")
    rendered = render_template(
        tmp_path_factory.mktemp("render"),
        opentofu="true",
        openspec="spec-driven",
        secrets_provider=request.param,
        **ANSWERS[request.param],
    )
    return request.param, rendered


def test_fnox_config_lists_the_values_and_never_exports_them(
    project: tuple[str, Path],
) -> None:
    provider, root = project
    config = root / "opentofu/fnox.toml"

    assert not (root / "opentofu/.env.example").exists()
    if provider == "none":
        assert not config.exists()
        return
    fnox = tomllib.loads(config.read_text())
    assert fnox["if_missing"] == "error"
    assert fnox["env"] == "exec"
    assert fnox["redact_exec"] is True
    assert fnox["daemon"] == {"enabled": True, "idle_timeout": "1h"}
    if provider == "proton-pass":
        assert fnox["providers"]["proton"]["vault"] == "demo-vault"
    else:
        assert fnox["providers"]["age"]["recipients"] == [RECIPIENT]


def test_only_none_loads_a_dotenv_file(project: tuple[str, Path]) -> None:
    provider, root = project
    env = tomllib.loads((root / "opentofu/mise.toml").read_text()).get("env", {})
    links = (root / ".worktreelinks").read_text()

    assert ("_" in env) == (provider == "none")
    assert ("opentofu/.env" in links) == (provider == "none")


def test_tools_match_the_provider(project: tuple[str, Path]) -> None:
    provider, root = project
    tools = tomllib.loads((root / "mise.toml").read_text())["tools"]
    required = (root / ".config/mise/required-tools").read_text().split()

    assert ("fnox" in tools) == (provider != "none")
    assert ("fnox>=1.50.0" in required) == (provider != "none")
    assert ("github:protonpass/pass-cli" in tools) == (provider == "proton-pass")
    if provider != "none":
        # Setup raises the seed to the minimum, because 1.48.0 crashes on macOS 15.
        assert tools["fnox"] == "latest"


def test_agent_and_spec_rules_match_the_provider(project: tuple[str, Path]) -> None:
    provider, root = project
    agents = (root / "AGENTS.md").read_text()
    openspec = (root / "openspec/config.yaml").read_text()

    assert ("`fnox get`" in agents) == (provider != "none")
    assert ("`pass-cli item view`" in agents) == (provider == "proton-pass")
    assert ("Ask before you write operator credentials" in agents) == (
        provider != "none"
    )
    assert ("operator password manager" in openspec) == (provider == "proton-pass")
    assert "Proton" not in openspec


@pytest.mark.parametrize("task", ["init", "plan", "apply"])
def test_task_wraps_only_tofu_in_fnox_exec(
    tmp_path: Path, project: tuple[str, Path], task: str
) -> None:
    provider, root = project
    calls = tmp_path / "calls"
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "tofu").write_text(f'#!/bin/sh\necho "tofu $*" >> {calls}\n')
    (tools / "fnox").write_text(
        f'#!/bin/sh\necho "fnox $*" >> {calls}\n'
        'while [ "$1" != -- ]; do shift; done\nshift\nexec "$@"\n'
    )
    for tool in tools.iterdir():
        tool.chmod(0o755)
    env = project_env()
    env.update(
        PATH=f"{tools}{os.pathsep}{env['PATH']}",
        TF_PLUGIN_CACHE_DIR=str(tmp_path / "cache"),
        # Skip the mise exec rerun that loads the OpenTofu env.
        OPENTOFU_TASK_ENV="1",
    )
    script = root / ".config/mise/tasks/opentofu" / task

    result = subprocess.run(  # noqa: S603
        ["bash", str(script), "-no-color"],  # noqa: S607
        cwd=root / "opentofu",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    [*wrapper, command] = calls.read_text().splitlines()
    assert command.startswith(f"tofu {task} -input=false")
    assert command.endswith(" -no-color")
    assert wrapper == ([] if provider == "none" else [f"fnox exec -- {command}"])


def run_hook(tmp_path: Path, root: Path, *, logged_in: bool) -> list[str]:
    """Run the post-start hook with a stub mise that answers `pass-cli info`."""
    hooks = tomllib.loads((root / ".config/wt.toml").read_text()).get("post-start", {})
    if "opentofu-init" not in hooks:
        return []
    calls = tmp_path / "calls"
    calls.touch()
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "mise").write_text(
        "#!/bin/sh\n"
        f'[ "$*" = "exec -- pass-cli info" ] && exit {0 if logged_in else 1}\n'
        f'echo "$* FNOX_NON_INTERACTIVE=$FNOX_NON_INTERACTIVE" >> {calls}\n'
    )
    (tools / "mise").chmod(0o755)
    env = {"PATH": f"{tools}{os.pathsep}{os.defpath}"}
    subprocess.run(  # noqa: S603
        ["sh", "-c", hooks["opentofu-init"]],  # noqa: S607
        cwd=root,
        env=env,
        check=True,
    )
    return calls.read_text().splitlines()


@pytest.mark.parametrize("logged_in", [True, False])
def test_worktree_hook_initializes_only_with_a_pass_session(
    tmp_path: Path, project: tuple[str, Path], logged_in: bool
) -> None:
    provider, root = project

    calls = run_hook(tmp_path, root, logged_in=logged_in)

    if provider == "proton-pass" and logged_in:
        assert calls == ["run opentofu:init FNOX_NON_INTERACTIVE=1"]
    else:
        assert calls == []


@pytest.mark.parametrize("vault", [None, ""])
def test_proton_pass_needs_a_vault(tmp_path: Path, vault: str | None) -> None:
    if shutil.which("copier") is None:
        pytest.skip("needs copier on PATH")
    answers = {} if vault is None else {"secrets_vault": vault}
    with pytest.raises(AssertionError, match="secrets_vault"):
        render_template(
            tmp_path, opentofu="true", secrets_provider="proton-pass", **answers
        )


@pytest.mark.parametrize(
    "recipient", ["", "age1short", "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5"]
)
def test_age_needs_a_public_key(tmp_path: Path, recipient: str) -> None:
    if shutil.which("copier") is None:
        pytest.skip("needs copier on PATH")
    with pytest.raises(AssertionError, match="Validation error for question"):
        render_template(
            tmp_path,
            opentofu="true",
            secrets_provider="age",
            secrets_age_recipient=recipient,
        )
