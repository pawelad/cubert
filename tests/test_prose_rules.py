"""Check the prose rules: the `spellchecker:disable-line` marker and the step order."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.support import ROOT, run

pytestmark = pytest.mark.skipif(shutil.which("pkl") is None, reason="needs pkl on PATH")

EM_DASH = "\u2014"
MARKER = "spellchecker:disable-line"


@pytest.fixture(scope="module")
def steps() -> dict[str, dict[str, Any]]:
    base = ROOT / "template/.config/hk/base.pkl"
    config: dict[str, Any] = json.loads(
        run(["pkl", "eval", "--format", "json", str(base)], ROOT)
    )
    return config["steps"]


def run_step(command: str, path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["bash", "-c", command.replace("{{files}}", path.name)],  # noqa: S607
        cwd=path.parent,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("step", "name", "line"),
    [
        ("no-british-english", "notes.md", "The card color is grey."),
        ("no-british-english-comments", "card.yaml", "# The card color is grey."),
        ("no-em-dashes", "notes.md", f"One {EM_DASH} two."),
        ("no-em-dashes-comments", "card.yaml", f"# One {EM_DASH} two."),
    ],
)
def test_prose_check_skips_only_marked_lines(
    tmp_path: Path,
    steps: dict[str, dict[str, Any]],
    step: str,
    name: str,
    line: str,
) -> None:
    path = tmp_path / name
    path.write_text(f"{line} # {MARKER}\n")

    assert run_step(steps[step]["check"], path).returncode == 0

    path.write_text(f"{line} # {MARKER}\n{line}\n")
    result = run_step(steps[step]["check"], path)

    assert result.returncode == 1
    assert result.stdout.splitlines() == [f"{name}:2:{line}"]


@pytest.mark.parametrize(
    ("step", "name", "line"),
    [
        ("no-em-dashes", "notes.md", f"One {EM_DASH} two."),
        ("no-em-dashes-comments", "card.yaml", f"# One {EM_DASH} two."),
    ],
)
def test_em_dash_fixer_leaves_marked_lines_as_written(
    tmp_path: Path,
    steps: dict[str, dict[str, Any]],
    step: str,
    name: str,
    line: str,
) -> None:
    path = tmp_path / name
    marked = f"{line} # {MARKER}"
    path.write_text(f"{marked}\n{line}\n")

    assert run_step(steps[step]["fix"], path).returncode == 0

    assert path.read_text() == f"{marked}\n{line.replace(EM_DASH, '-')}\n"


@pytest.mark.parametrize(
    ("twin", "full"),
    [
        ("fix-smart-quotes-comments", "fix-smart-quotes"),
        ("no-british-english-comments", "no-british-english"),
        ("no-em-dashes-comments", "no-em-dashes"),
        ("no-emojis-comments", "no-emojis"),
    ],
)
def test_comment_twin_runs_after_its_full_file_step(
    steps: dict[str, dict[str, Any]], twin: str, full: str
) -> None:
    assert steps[twin]["depends"] == [full]
