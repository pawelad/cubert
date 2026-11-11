"""Load a script that has no package as a module, so tests can call its functions."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path
from types import ModuleType


def load_script(path: str) -> ModuleType:
    """Import the script at `path` under its file stem."""
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parent.parent
MISE_PROJECT_VARS = (
    "MISE_PROJECT_ROOT",
    "MISE_CONFIG_ROOT",
    "MISE_ORIGINAL_CWD",
    "MISE_TASK_NAME",
    "MISE_TASK_DIR",
    "MISE_TASK_FILE",
)


def project_env() -> dict[str, str]:
    """Return an environment where nested mise runs resolve the project, not cubert."""
    env = {k: v for k, v in os.environ.items() if k not in MISE_PROJECT_VARS}
    # Copier and the project commit in temporary repos, where global hk hooks would run.
    env["HK"] = "0"
    return env


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    """Run a command, fail with its output if it fails, and return stdout and stderr."""
    result = subprocess.run(  # noqa: S603
        command,
        cwd=cwd,
        env=env or project_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"{command} failed:\n{output}"
    return output


def snapshot_template(dest: Path) -> str:
    """Commit a copy of the working tree in `dest` and return the commit.

    Copier renders only a commit, and the working tree holds the change under test.
    """
    files = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    for raw in filter(None, files):
        name = raw.decode()
        source = ROOT / name
        if not source.exists() and not source.is_symlink():
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(source.readlink())
        else:
            shutil.copy2(source, target)
    run(["git", "-c", "init.defaultBranch=main", "init", "--quiet"], dest)
    run(["git", "add", "--all"], dest)
    run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet",
         "--no-verify", "-m", "chore: base"],
        dest,
    )  # fmt: skip
    return run(["git", "rev-parse", "HEAD"], dest).strip()


def render_template(tmp_path: Path, **answers: str) -> Path:
    """Render the working tree of cubert into `tmp_path/project` and return it."""
    source = tmp_path / "cubert"
    source.mkdir()
    ref = snapshot_template(source)
    project = tmp_path / "project"
    data = {"project_name": "demo", "description": "A demo project.", **answers}
    command = ["copier", "copy", "--quiet", "--defaults", "--vcs-ref", ref]
    for key, value in data.items():
        command += ["-d", f"{key}={value}"]
    run([*command, str(source), str(project)], tmp_path)
    return project
