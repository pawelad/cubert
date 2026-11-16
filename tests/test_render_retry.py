"""Retry transient mise downloads and preserve deterministic failures."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.support import ROOT, project_env


@pytest.mark.parametrize(
    ("error", "retry"),
    [
        ("lock-time provenance verification failed", True),
        (
            (
                "Failed to install core:python@3.14: HTTP status client error "
                "(403 Forbidden) for url (https://github.com/astral-sh/"
                "python-build-standalone/releases/download/20261110/python.tar.gz)"
            ),
            True,
        ),
        (
            "HTTP status client error (403 Forbidden) for url (https://example.com)",
            False,
        ),
        ("template validation failed", False),
    ],
)
def test_render_download_retry(tmp_path: Path, error: str, retry: bool) -> None:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    copier = binaries / "copier"
    copier.write_text(
        '#!/bin/bash\nprintf "attempt\\n" >> "$ATTEMPTS"\n'
        'echo "$DOWNLOAD_ERROR" >&2\nexit 1\n'
    )
    sleeper = binaries / "sleep"
    sleeper.write_text('#!/bin/bash\nprintf "%s\\n" "$1" >> "$DELAYS"\n')
    copier.chmod(0o755)
    sleeper.chmod(0o755)
    attempts = tmp_path / "attempts"
    delays = tmp_path / "delays"
    env = project_env()
    env.update(
        PATH=f"{binaries}{os.pathsep}{env['PATH']}",
        ATTEMPTS=str(attempts),
        DELAYS=str(delays),
        DOWNLOAD_ERROR=error,
    )
    name = "p0d0t0a0c0s0_none"
    out = tmp_path / "renders"

    result = subprocess.run(  # noqa: S603
        ["bash", str(ROOT / "scripts/render.sh"), str(ROOT), str(out), name],  # noqa: S607
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert attempts.read_text().splitlines() == ["attempt"] * (2 if retry else 1)
    assert (out / f"{name}.log").read_text().strip() == error
    assert (out / f"{name}.log.first").exists() == retry
    if retry:
        assert delays.read_text() == "60\n"
        assert (out / f"{name}.log.first").read_text().strip() == error
        assert "retry" in result.stdout
    else:
        assert not delays.exists()
