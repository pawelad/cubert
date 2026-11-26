"""Test the docker-pins check that hk runs on mise.toml and Dockerfiles."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from tests.support import load_script

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

check_docker_pins = load_script("template/.config/hk/checks/check_docker_pins.py")

MISE = '[tools]\nuv = "0.13.9"\ngolangci-lint = "2.6.1"\n"npm:dclint" = "3.1.0"\n'


def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dockerfile: str) -> Path:
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)  # noqa: S607
    (tmp_path / "mise.toml").write_text(MISE)
    path = tmp_path / "apps" / "backend" / "Dockerfile"
    path.parent.mkdir(parents=True)
    path.write_text(dockerfile)
    monkeypatch.chdir(tmp_path)
    return path


def test_matching_arg_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project(
        tmp_path,
        monkeypatch,
        "ARG UV_VERSION=0.13.9\nFROM ghcr.io/astral-sh/uv:${UV_VERSION}\n",
    )
    assert check_docker_pins.main([]) == 0


def test_drifted_arg_fails_with_the_exact_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project(tmp_path, monkeypatch, "# syntax\nARG UV_VERSION=0.13.7\n")
    assert check_docker_pins.main([]) == 1
    assert capsys.readouterr().out == (
        "apps/backend/Dockerfile:2: ARG UV_VERSION=0.13.7 does not match mise.toml uv"
        " (0.13.9). Fix: ARG UV_VERSION=0.13.9\n"
    )


def test_dashed_tool_name_maps_to_underscores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project(tmp_path, monkeypatch, "ARG GOLANGCI_LINT_VERSION=2.5.0\n")
    assert check_docker_pins.main([]) == 1
    assert "mise.toml golangci-lint (2.6.1)" in capsys.readouterr().out


def test_args_without_a_plain_mise_tool_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dockerfile = (
        "ARG APP_VERSION=\nARG NODE_VERSION=24.1.0\nARG DCLINT_VERSION=1.0.0\n"
        "ARG UV_VERSION\nARG UV_VERSION=${BASE_UV_VERSION}\narg uv_version=0.1.0\n"
    )
    project(tmp_path, monkeypatch, dockerfile)
    assert check_docker_pins.main([]) == 0


def test_quoted_and_v_prefixed_args_compare_by_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project(
        tmp_path, monkeypatch, 'ARG UV_VERSION="v0.13.9"\nARG UV_VERSION="v0.1.0"\n'
    )
    assert check_docker_pins.main([]) == 1
    assert capsys.readouterr().out.endswith('Fix: ARG UV_VERSION="v0.13.9"\n')


def test_fix_rewrites_only_drifted_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = project(
        tmp_path, monkeypatch, "ARG UV_VERSION=0.13.7\nARG APP_VERSION=1\nRUN true"
    )
    assert check_docker_pins.main(["--fix"]) == 0
    assert path.read_text() == "ARG UV_VERSION=0.13.9\nARG APP_VERSION=1\nRUN true"
    assert check_docker_pins.main([]) == 0


def test_ignored_dockerfiles_are_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project(tmp_path, monkeypatch, "ARG UV_VERSION=0.13.9\n")
    (tmp_path / ".gitignore").write_text("vendor/\n")
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "Dockerfile.dev").write_text("ARG UV_VERSION=0.1.0\n")
    assert check_docker_pins.main([]) == 0
    (tmp_path / "Dockerfile.dev").write_text("ARG UV_VERSION=0.1.0\n")
    assert check_docker_pins.main([]) == 1


def test_v_prefixed_pin_keeps_a_bare_arg_bare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project(tmp_path, monkeypatch, "ARG UV_VERSION=0.1.0\n")
    (tmp_path / "mise.toml").write_text('[tools]\nuv = "v0.13.9"\n')
    assert check_docker_pins.main([]) == 1
    assert capsys.readouterr().out.endswith("Fix: ARG UV_VERSION=0.13.9\n")


def test_single_quoted_arg_compares_by_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = project(
        tmp_path,
        monkeypatch,
        "ARG UV_VERSION='0.13.9'\nARG GOLANGCI_LINT_VERSION='1'\n",
    )
    assert check_docker_pins.main(["--fix"]) == 0
    assert (
        path.read_text()
        == "ARG UV_VERSION='0.13.9'\nARG GOLANGCI_LINT_VERSION='2.6.1'\n"
    )


def test_unpinned_tool_request_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = project(tmp_path, monkeypatch, "ARG NODE_VERSION=24.22.1\n")
    (tmp_path / "mise.toml").write_text('[tools]\nnode = "lts"\n')
    assert check_docker_pins.main(["--fix"]) == 0
    assert path.read_text() == "ARG NODE_VERSION=24.22.1\n"


def test_named_dockerfiles_are_checked_and_templates_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project(tmp_path, monkeypatch, "ARG UV_VERSION=0.13.9\n")
    (tmp_path / "Dockerfile.j2").write_text("ARG UV_VERSION=0.1.0\n")
    (tmp_path / "Dockerfile.jinja").write_text("ARG UV_VERSION=0.1.0\n")
    assert check_docker_pins.main([]) == 0
    (tmp_path / "worker.Dockerfile").write_text("ARG UV_VERSION=0.1.0\n")
    assert check_docker_pins.main([]) == 1
