"""Check that setup pins the release that minimum_release_age allows (stub mise)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import project_env, render_template

pytestmark = pytest.mark.skipif(
    shutil.which("copier") is None or shutil.which("uv") is None,
    reason="needs copier and uv on PATH",
)

# `mise latest` applies the cutoff. hk 2.12.0 stands in for the newest allowed release,
# and young-tool has no release that old.
STUB_MISE = """#!/bin/sh
printf '%s\\n' "$*" >> "$CALLS"
case "$1" in
  latest)
    case "$2" in hk*) echo 2.12.0 ;; young-tool*) exit 1 ;; *) echo 1.0.0 ;; esac ;;
esac
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return render_template(tmp_path)


def run_setup(
    tmp_path: Path, project: Path, config: str | None, required: str = ""
) -> list[list[str]]:
    """Run setup with the stub and return the `mise use` requests, one list per call."""
    if config is not None:
        (project / "mise.toml").write_text(config)
    with (project / ".config/mise/required-tools").open("a") as file:
        file.write(required)
    tools = tmp_path / "bin"
    tools.mkdir(exist_ok=True)
    (tools / "mise").write_text(STUB_MISE)
    (tools / "mise").chmod(0o755)
    calls = tmp_path / "calls"
    env = project_env()
    env.update(PATH=f"{tools}{os.pathsep}{env['PATH']}", CALLS=str(calls), CI="1")
    subprocess.run(["git", "init", "--quiet"], cwd=project, check=True)  # noqa: S607
    result = subprocess.run(
        ["bash", ".config/mise/tasks/setup"],  # noqa: S607
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    prefix = "use --path mise.toml --pin "
    return [
        line.removeprefix(prefix).split()
        for line in calls.read_text().splitlines()
        if line.startswith(prefix)
    ]


def test_setup_pins_seeded_latest_tools_to_their_allowed_release(
    tmp_path: Path, project: Path
) -> None:
    [requests] = run_setup(tmp_path, project, None)

    assert "hk@2.12.0" in requests
    assert not [r for r in requests if r.endswith(("@latest", "@lts"))]


def test_setup_pins_added_tools_with_their_options_and_scopes(
    tmp_path: Path, project: Path
) -> None:
    requests = run_setup(tmp_path, project, '[tools]\nuv = "1.0.0"\n')

    added = requests[-1]
    assert "hk@2.12.0" in added
    assert "node@1.0.0" in added
    assert "yamllint[python=3.14]@1.0.0" in added
    assert "npm:@fission-ai/openspec@1.0.0" in added


# The stub's newest allowed fnox is 1.0.0, below the minimum that the list sets.
def test_setup_raises_an_added_tool_to_its_minimum(
    tmp_path: Path, project: Path
) -> None:
    requests = run_setup(tmp_path, project, '[tools]\nuv = "1.0.0"\n', "fnox>=1.50.0\n")

    added = requests[-1]
    assert "fnox@1.50.0" in added
    assert "hk@2.12.0" in added


def test_setup_raises_a_seeded_tool_to_its_minimum_in_one_pass(
    tmp_path: Path, project: Path
) -> None:
    [requests] = run_setup(tmp_path, project, None, "dprint>=2.0.0\n")

    assert "dprint@2.0.0" in requests


def test_setup_pins_the_minimum_when_the_cutoff_hides_every_release(
    tmp_path: Path, project: Path
) -> None:
    requests = run_setup(
        tmp_path, project, '[tools]\nuv = "1.0.0"\n', "young-tool>=3.0.0\n"
    )

    assert "young-tool@3.0.0" in requests[-1]
