"""Check that mypy runs each PEP 723 script against its own inline dependencies."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import load_script

check_mypy = load_script("template/.config/hk/checks/check_mypy.py")

SCRIPT = '# /// script\n# dependencies = [{deps}]\n# ///\n"""Demo."""\n\n'
PROJECT = """\
[project]
name = "demo"
version = "0.0.0"
requires-python = ">=3.11"

[dependency-groups]
dev = ["mypy"]

[tool.uv]
package = false

[tool.mypy]
strict = true
"""


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (SCRIPT.format(deps='"rich"'), {"dependencies": ["rich"]}),
        ("# /// script\n#\n# ///\n", {}),
        ('"""A module."""\n', None),
        ("# /// pyproject\n# [x]\n# ///\n", None),
        ("x = 1  # /// script\n", None),
    ],
)
def test_script_metadata_reads_a_script_block(
    tmp_path: Path, text: str, expected: dict[str, object] | None
) -> None:
    assert check_mypy.script_metadata(write(tmp_path / "a.py", text)) == expected


def test_script_metadata_skips_a_stub(tmp_path: Path) -> None:
    path = write(tmp_path / "a.pyi", "# /// script\n#\n# ///\n")

    assert check_mypy.script_metadata(path) is None


@pytest.mark.parametrize(
    ("requires", "expected"),
    [(">=3.11", "3.11"), (">= 3.12, <4", "3.12"), ("~=3.13", None), (None, None)],
)
def test_minimum_python_reads_the_lower_bound(
    requires: str | None, expected: str | None
) -> None:
    metadata = {} if requires is None else {"requires-python": requires}

    assert check_mypy.minimum_python(metadata) == expected


@pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv on PATH")
class TestMain:
    # The demo project has no uv.lock, so ci:check's UV_LOCKED would fail every uv call.
    @pytest.fixture(autouse=True)
    def project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        unlocked = {"UV_LOCKED", "UV_FROZEN"}
        for name in unlocked:
            monkeypatch.delenv(name, raising=False)
        env = {k: v for k, v in check_mypy.BASE_ENV.items() if k not in unlocked}
        monkeypatch.setattr(check_mypy, "BASE_ENV", env)
        write(tmp_path / "pyproject.toml", PROJECT)
        monkeypatch.chdir(tmp_path)

    def test_script_with_its_dependency_passes(self) -> None:
        body = "import rich\n\nVERSION: str = rich.__name__\n"
        write(Path("s/ok.py"), SCRIPT.format(deps='"rich"') + body)

        assert check_mypy.main(["s/ok.py"]) == 0

    # ci:check sets UV_LOCKED, and `uv sync --script` would then demand a script lock.
    def test_unlocked_script_syncs_under_uv_locked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(check_mypy, "BASE_ENV", {**os.environ, "UV_LOCKED": "1"})
        path = write(Path("s/ok.py"), SCRIPT.format(deps='"rich"'))

        assert check_mypy.script_python(path) is not None

    # mypy is in the project env, so only the script's own env makes this fail.
    def test_script_import_missing_from_its_block_fails(self) -> None:
        write(Path("s/bad.py"), SCRIPT.format(deps="") + "import mypy\n")

        assert check_mypy.main(["s/bad.py"]) == 1

    # mypy 2.x accepts --python-version 3.10 or later, so 3.9 checks as mypy's floor.
    def test_script_below_mypys_oldest_target_passes(self) -> None:
        block = '# /// script\n# requires-python = ">=3.9"\n# ///\n'
        write(Path("s/old.py"), block + '"""Demo."""\n\nX: int = 1\n')

        assert check_mypy.main(["s/old.py"]) == 0

    # itertools.batched is new in 3.12, so a script that allows 3.11 cannot use it.
    def test_script_is_checked_for_its_oldest_python(self) -> None:
        block = '# /// script\n# requires-python = ">=3.11"\n# ///\n'
        write(Path("s/new.py"), block + "from itertools import batched\n")

        assert check_mypy.main(["s/new.py"]) == 1

    def test_stale_script_lock_fails_and_stays_unchanged(self) -> None:
        path = write(Path("s/ok.py"), SCRIPT.format(deps=""))
        subprocess.run(["uv", "lock", "--script", str(path)], check=True)  # noqa: S603, S607
        lock = path.with_name("ok.py.lock").read_text()
        write(path, SCRIPT.format(deps='"rich"'))

        assert check_mypy.main([str(path)]) == 1
        assert path.with_name("ok.py.lock").read_text() == lock

    def test_plain_file_runs_in_the_project_env(self) -> None:
        write(Path("ok.py"), '"""Demo."""\n\nimport mypy\n')
        write(Path("bad.py"), '"""Demo."""\n\nX: int = "a"\n')

        assert check_mypy.main(["ok.py"]) == 0
        assert check_mypy.main(["ok.py", "bad.py"]) == 1
