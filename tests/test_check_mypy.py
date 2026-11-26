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

# A host runs these files on its own Python, older than the project's.
TARGETS = """
[tool.ruff.per-file-target-version]
"hosts/**/*.py" = "py311"
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


class TestPlainPython:
    @pytest.fixture(autouse=True)
    def project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        check_mypy.ruff_targets.cache_clear()
        monkeypatch.setattr(check_mypy, "mypy_minimum", lambda: "3.10")
        monkeypatch.chdir(tmp_path)

    def test_glob_selects_the_python(self) -> None:
        write(Path("pyproject.toml"), PROJECT + TARGETS)

        assert check_mypy.plain_python(Path("hosts/zapp/run.py")) == "3.11"
        assert check_mypy.plain_python(Path("hosts/run.py")) == "3.11"
        assert check_mypy.plain_python(Path("app/run.py")) is None

    def test_leading_double_star_matches_a_root_file(self) -> None:
        write(Path("ruff.toml"), '[per-file-target-version]\n"**/*.py" = "py311"\n')

        assert check_mypy.plain_python(Path("run.py")) == "3.11"

    def test_glob_matches_a_file_name_anywhere(self) -> None:
        write(Path("ruff.toml"), '[per-file-target-version]\n"legacy.py" = "py311"\n')

        assert check_mypy.plain_python(Path("a/b/legacy.py")) == "3.11"

    def test_target_below_mypys_floor_checks_as_the_floor(self) -> None:
        write(Path("ruff.toml"), '[per-file-target-version]\n"*.py" = "py38"\n')

        assert check_mypy.plain_python(Path("old.py")) == "3.10"

    # ruff reads the first config in a directory and ignores the rest.
    def test_ruff_toml_takes_precedence_over_pyproject(self) -> None:
        write(Path("pyproject.toml"), PROJECT + TARGETS)
        write(Path("ruff.toml"), "line-length = 88\n")

        assert check_mypy.plain_python(Path("hosts/zapp/run.py")) is None

    def test_pyproject_without_a_ruff_table_is_skipped(self) -> None:
        write(Path("pyproject.toml"), PROJECT)

        assert check_mypy.plain_python(Path("run.py")) is None


class TestModuleName:
    def test_plain_file_is_named_after_its_stem(self, tmp_path: Path) -> None:
        assert check_mypy.module_name(write(tmp_path / "lib/mod.py", "")) == "mod"

    def test_package_file_is_named_after_its_packages(self, tmp_path: Path) -> None:
        write(tmp_path / "src/pkg/__init__.pyi", "")
        init = write(tmp_path / "src/pkg/sub/__init__.py", "")
        path = write(tmp_path / "src/pkg/sub/mod.py", "")

        assert check_mypy.module_name(path) == "pkg.sub.mod"
        assert check_mypy.module_name(init) == "pkg.sub"

    def test_package_climb_stops_at_a_folder_that_is_not_an_identifier(
        self, tmp_path: Path
    ) -> None:
        write(tmp_path / "my-app/__init__.py", "")
        write(tmp_path / "my-app/pkg/__init__.py", "")
        path = write(tmp_path / "my-app/pkg/mod.py", "")

        assert check_mypy.module_name(path) == "pkg.mod"

    def test_stub_only_package_drops_its_stubs_suffix(self, tmp_path: Path) -> None:
        write(tmp_path / "pkg-stubs/__init__.pyi", "")

        assert check_mypy.module_name(tmp_path / "pkg-stubs/mod.pyi") == "pkg.mod"

    def test_symlinked_file_is_named_from_its_own_folder(self, tmp_path: Path) -> None:
        write(tmp_path / "pkg/__init__.py", "")
        target = write(tmp_path / "pkg/mod.py", "")
        (tmp_path / "lib").mkdir()
        link = tmp_path / "lib/mod.py"
        link.symlink_to(target)

        assert check_mypy.module_name(link) == "mod"


class TestWithoutClashes:
    @pytest.fixture(autouse=True)
    def project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        check_mypy.ruff_targets.cache_clear()
        monkeypatch.chdir(tmp_path)

    def test_group_without_a_clash_runs_one_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[str, ...]] = []

        def mypy(*args: str) -> int:
            calls.append(args)
            return 0

        monkeypatch.setattr(check_mypy, "mypy", mypy)
        files = ["a/one.py", "b/two.py", "c/three.py"]
        for path in files:
            write(Path(path), "")

        assert check_mypy.main(files) == 0
        assert calls == [tuple(files)]

    def test_same_named_files_go_to_separate_calls(self) -> None:
        files = ["lib/mod.py", "a/mod.py", "lib/other.py", "b/mod.py", "a/other.py"]
        for path in files:
            write(Path(path), "")

        assert check_mypy.without_clashes(files) == [
            ["lib/mod.py", "lib/other.py"],
            ["a/mod.py", "a/other.py"],
            ["b/mod.py"],
        ]

    def test_same_named_modules_in_different_packages_do_not_clash(self) -> None:
        for path in ("p/__init__.py", "q/__init__.py", "p/mod.py", "q/mod.py"):
            write(Path(path), "")

        assert check_mypy.without_clashes(["p/mod.py", "q/mod.py"]) == [
            ["p/mod.py", "q/mod.py"]
        ]


@pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv on PATH")
class TestMain:
    # The demo project has no uv.lock, so an exported UV_LOCKED would fail each uv call.
    @pytest.fixture(autouse=True)
    def project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        unlocked = {"UV_LOCKED", "UV_FROZEN"}
        for name in unlocked:
            monkeypatch.delenv(name, raising=False)
        env = {k: v for k, v in check_mypy.BASE_ENV.items() if k not in unlocked}
        monkeypatch.setattr(check_mypy, "BASE_ENV", env)
        # A fixed default, so a file outside the targets does not depend on uv's Python.
        project = PROJECT.replace(
            "strict = true", 'strict = true\npython_version = "3.12"'
        )
        write(tmp_path / "pyproject.toml", project + TARGETS)
        check_mypy.ruff_targets.cache_clear()
        monkeypatch.chdir(tmp_path)

    def test_script_with_its_dependency_passes(self) -> None:
        body = "import rich\n\nVERSION: str = rich.__name__\n"
        write(Path("s/ok.py"), SCRIPT.format(deps='"rich"') + body)

        assert check_mypy.main(["s/ok.py"]) == 0

    # A project can export UV_LOCKED, and `uv sync --script` would then demand a lock.
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

    # itertools.batched is new in 3.12, and ruff targets 3.11 for files under hosts/.
    def test_plain_file_is_checked_for_its_ruff_target(self) -> None:
        write(Path("app.py"), '"""Demo."""\n\nfrom itertools import batched\n')
        write(Path("hosts/zapp/run.py"), "from itertools import batched\n")

        assert check_mypy.main(["app.py"]) == 0
        assert check_mypy.main(["app.py", "hosts/zapp/run.py"]) == 1

    # Two copies of one module, as a shared lib/ file and a copy next to its script.
    def test_same_named_plain_files_in_different_folders_pass(self) -> None:
        write(Path("lib/shared.py"), '"""Demo."""\n\nX: int = 1\n')
        write(Path("tool/shared.py"), '"""Demo."""\n\nX: int = 1\n')

        assert check_mypy.main(["lib/shared.py", "tool/shared.py"]) == 0

    def test_error_in_a_split_off_copy_fails(self) -> None:
        write(Path("lib/shared.py"), '"""Demo."""\n\nX: int = 1\n')
        write(Path("tool/shared.py"), '"""Demo."""\n\nX: int = "a"\n')

        assert check_mypy.main(["lib/shared.py", "tool/shared.py"]) == 1
