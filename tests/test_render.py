"""Check that answers with quotes and backslashes render into valid files."""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest

from tests.support import render_template

pytestmark = pytest.mark.skipif(
    shutil.which("copier") is None, reason="needs copier on PATH"
)

TRICKY = 'A "quoted" project with a \\ backslash.'


def test_description_with_quotes_renders_valid_pyproject(tmp_path: Path) -> None:
    project = render_template(tmp_path, python="true", description=TRICKY)

    parsed = tomllib.loads((project / "pyproject.toml").read_text())

    assert parsed["project"]["description"] == TRICKY
