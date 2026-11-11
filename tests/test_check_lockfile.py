"""Check native tool graphs without relying on the local mise installation cache."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.support import load_script

check_lockfile = load_script("template/.config/hk/checks/check_lockfile.py")


def lock_with_graph(
    tmp_path: Path, backend: str, content: bytes = b"version = 1\n"
) -> Path:
    key, native, manifest = check_lockfile.GRAPHS[backend]
    directory = tmp_path / ".mise/locks/tool/1.2.3"
    directory.mkdir(parents=True)
    (directory / native).write_bytes(content)
    (directory / manifest).write_text("{}\n")
    digest = hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()
    path = tmp_path / "mise.lock"
    path.write_text(
        'lockfile_version = 3\n[[tools.tool]]\nversion = "1.2.3"\n'
        f'backend = "{backend}:tool"\n'
        f'{key} = {{ path = ".mise/locks/tool/1.2.3", digest = "sha256:{digest}" }}\n'
    )
    return path


@pytest.mark.parametrize("backend", ["pypi", "pipx", "npm"])
def test_complete_native_graph_passes(tmp_path: Path, backend: str) -> None:
    assert check_lockfile.failures(lock_with_graph(tmp_path, backend)) == []


def test_crlf_graph_uses_the_normalized_digest(tmp_path: Path) -> None:
    assert (
        check_lockfile.failures(lock_with_graph(tmp_path, "pypi", b"version = 1\r\n"))
        == []
    )


def test_version_only_python_entry_fails(tmp_path: Path) -> None:
    path = tmp_path / "mise.lock"
    path.write_text(
        'lockfile_version = 3\n[[tools.tool]]\nversion = "1.2.3"\n'
        'backend = "pypi:tool"\n'
    )
    assert "has no uv dependency graph" in check_lockfile.failures(path)[0]


@pytest.mark.parametrize("missing", ["uv.lock", "pyproject.toml"])
def test_missing_native_file_fails(tmp_path: Path, missing: str) -> None:
    path = lock_with_graph(tmp_path, "pypi")
    (tmp_path / ".mise/locks/tool/1.2.3" / missing).unlink()
    assert check_lockfile.failures(path)


def test_changed_graph_fails(tmp_path: Path) -> None:
    path = lock_with_graph(tmp_path, "pypi")
    (tmp_path / ".mise/locks/tool/1.2.3/uv.lock").write_text("changed\n")
    assert "digest does not match" in check_lockfile.failures(path)[0]


def test_missing_lockfile_fails(tmp_path: Path) -> None:
    assert "cannot read lockfile" in check_lockfile.failures(tmp_path / "mise.lock")[0]


def test_legacy_lockfile_without_native_graphs_passes(tmp_path: Path) -> None:
    path = tmp_path / "mise.lock"
    path.write_text('[[tools.tool]]\nversion = "1.2.3"\nbackend = "pypi:tool"\n')
    assert check_lockfile.failures(path) == []
