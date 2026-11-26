"""Check that ansible:install installs exactly the pinned collections."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.support import load_script, project_env, render_template

pytestmark = pytest.mark.skipif(
    shutil.which("copier") is None or shutil.which("pkl") is None,
    reason="needs copier and pkl on PATH",
)

check_collections = load_script("template/.config/hk/checks/check_collections.py")

TASK = ".config/mise/tasks/ansible/install"
LIVE = "ansible/collections/ansible_collections"
# ansible-core ships PyYAML. JSON is YAML, so the stub parses the fixtures.
YAML_STUB = "import json\n\n\ndef safe_load(stream):\n    return json.load(stream)\n"
FAKE_ANSIBLE = f"""#!/bin/sh
echo "  python version = 3.14.0 (main) [Clang] ({sys.executable})"
"""
FAKE_CONFIG = """#!/bin/sh
echo "COLLECTIONS_PATHS(ansible.cfg) = ['$FAKE_FIRST_PATH', '/elsewhere']"
"""
# Installs each pin from requirements.yml as Galaxy lays it out, or fails midway.
FAKE_GALAXY = f"""#!{sys.executable}
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ["GALAXY_CALLS"], "a") as log:
    log.write(json.dumps([args, os.environ.get("ANSIBLE_COLLECTIONS_PATH")]) + "\\n")
root = pathlib.Path(args[args.index("-p") + 1]) / "ansible_collections"
entries = json.loads(pathlib.Path("requirements.yml").read_text())["collections"]
if os.environ.get("GALAXY_DEPENDENCY"):
    entries.append({{"name": os.environ["GALAXY_DEPENDENCY"], "version": "9.9.9"}})
for entry in entries:
    namespace, name = entry["name"].split(".")
    (root / namespace / name).mkdir(parents=True)
    if os.environ.get("GALAXY_FAIL"):
        sys.exit("ERROR! Galaxy is unreachable")
    info = {{"namespace": namespace, "name": name, "version": entry["version"]}}
    manifest = {{"collection_info": info}}
    (root / namespace / name / "MANIFEST.json").write_text(json.dumps(manifest))
    meta = root / f"{{entry['name']}}-{{entry['version']}}.info"
    meta.mkdir()
    (meta / "GALAXY.yml").write_text("")
"""


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render_template(
        tmp_path_factory.mktemp("render"), ansible="true", openspec="none"
    )


@pytest.fixture
def project(tmp_path: Path, rendered: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(rendered, project, symlinks=True)
    (project / "ansible").mkdir(exist_ok=True)
    return project


def tools(tmp_path: Path) -> Path:
    """Write each fake Ansible tool that a test did not write itself."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name, body in [
        ("ansible", FAKE_ANSIBLE),
        ("ansible-config", FAKE_CONFIG),
        ("ansible-galaxy", FAKE_GALAXY),
    ]:
        if (bin_dir / name).exists():
            continue
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    (tmp_path / "stub").mkdir()
    (tmp_path / "stub/yaml.py").write_text(YAML_STUB)
    return bin_dir


def pin(project: Path, **versions: str) -> None:
    collections = [{"name": name, "version": v} for name, v in versions.items()]
    (project / "ansible/requirements.yml").write_text(
        json.dumps({"collections": collections})
    )


def install(project: Path, name: str, version: str, *, manifest: bool = True) -> Path:
    namespace, short = name.split(".")
    path = project / LIVE / namespace / short
    path.mkdir(parents=True)
    if manifest:
        info = {"namespace": namespace, "name": short, "version": version}
        (path / "MANIFEST.json").write_text(json.dumps({"collection_info": info}))
    else:
        (path / "galaxy.yml").write_text(f"namespace: {namespace}\nname: {short}\n")
    return path


def run_task(
    tmp_path: Path, project: Path, first: str | None = None, **env: str
) -> subprocess.CompletedProcess[str]:
    bin_dir = tools(tmp_path)
    full = project_env()
    full.update(
        PATH=f"{bin_dir}{os.pathsep}{full['PATH']}",
        PYTHONPATH=str(tmp_path / "stub"),
        GALAXY_CALLS=str(tmp_path / "galaxy-calls"),
        FAKE_FIRST_PATH=first or str((project / "ansible/collections").resolve()),
        **env,
    )
    return subprocess.run(  # noqa: S603
        [str(project / TASK)],
        cwd=project,
        env=full,
        capture_output=True,
        text=True,
        check=False,
    )


def galaxy_calls(tmp_path: Path) -> list[list[object]]:
    log = tmp_path / "galaxy-calls"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines()]


def installed(project: Path) -> dict[str, str]:
    found: dict[str, str] = check_collections.installed(project / "ansible/collections")
    return found


def test_install_replaces_unpinned_and_drifted_collections(
    tmp_path: Path, project: Path
) -> None:
    pin(project, **{"demo.kept": "1.0.0", "demo.bumped": "2.0.0"})
    install(project, "demo.bumped", "1.0.0")
    install(project, "old.gone", "1.0.0")

    result = run_task(tmp_path, project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert installed(project) == {"demo.bumped": "2.0.0", "demo.kept": "1.0.0"}
    assert not (project / LIVE / "old").exists()
    assert sorted(p.name for p in (project / LIVE).glob("*.info")) == [
        "demo.bumped-2.0.0.info",
        "demo.kept-1.0.0.info",
    ]
    assert not (project / "ansible/collections/.staging").exists()
    [[_, collections_path]] = galaxy_calls(tmp_path)
    assert str(collections_path).endswith("ansible/collections/.staging")


def test_install_keeps_a_collection_without_a_manifest(
    tmp_path: Path, project: Path
) -> None:
    pin(project, **{"demo.pinned": "1.0.0"})
    source = install(project, "demo.util", "1.0.0", manifest=False)

    result = run_task(tmp_path, project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (source / "galaxy.yml").is_file()
    assert installed(project) == {"demo.pinned": "1.0.0"}


def test_install_skips_galaxy_when_the_set_matches(
    tmp_path: Path, project: Path
) -> None:
    pin(project, **{"demo.kept": "1.0.0"})
    install(project, "demo.kept", "1.0.0")

    result = run_task(tmp_path, project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "match requirements.yml" in result.stdout
    assert galaxy_calls(tmp_path) == []


def test_failed_download_keeps_the_installed_set(tmp_path: Path, project: Path) -> None:
    pin(project, **{"demo.new": "2.0.0"})
    install(project, "demo.old", "1.0.0")

    result = run_task(tmp_path, project, GALAXY_FAIL="1")

    assert result.returncode != 0
    assert "Galaxy is unreachable" in result.stderr
    assert installed(project) == {"demo.old": "1.0.0"}
    assert not (project / "ansible/collections/.staging").exists()


def test_install_fails_when_ansible_looks_elsewhere_first(
    tmp_path: Path, project: Path
) -> None:
    pin(project, **{"demo.new": "1.0.0"})

    result = run_task(tmp_path, project, first="/home/me/.ansible/collections")

    assert result.returncode == 1
    assert "collections_path = ./collections" in result.stderr
    assert galaxy_calls(tmp_path) == []


def test_install_rejects_a_version_range_before_downloading(
    tmp_path: Path, project: Path
) -> None:
    pin(project, **{"demo.loose": ">=1.0.0"})

    result = run_task(tmp_path, project)

    assert result.returncode == 2
    assert "demo.loose needs an exact version" in result.stderr
    assert galaxy_calls(tmp_path) == []


def test_install_does_nothing_without_requirements(
    tmp_path: Path, project: Path
) -> None:
    result = run_task(tmp_path, project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert galaxy_calls(tmp_path) == []


def test_install_removes_collections_once_requirements_are_gone(
    tmp_path: Path, project: Path
) -> None:
    install(project, "old.gone", "1.0.0")
    source = install(project, "demo.util", "1.0.0", manifest=False)

    result = run_task(tmp_path, project)

    assert result.returncode == 0, result.stdout + result.stderr
    assert installed(project) == {}
    assert (source / "galaxy.yml").is_file()


def test_unpinned_dependency_stops_before_the_swap(
    tmp_path: Path, project: Path
) -> None:
    pin(project, **{"demo.new": "2.0.0"})
    install(project, "demo.old", "1.0.0")

    result = run_task(tmp_path, project, GALAXY_DEPENDENCY="demo.dependency")

    assert result.returncode == 2
    assert "demo.dependency: 9.9.9 installed, not in requirements.yml" in result.stderr
    assert "dependencies included" in result.stderr
    assert installed(project) == {"demo.old": "1.0.0"}
    assert not (project / "ansible/collections/.staging").exists()


def test_install_reports_a_failing_ansible_config(
    tmp_path: Path, project: Path
) -> None:
    pin(project, **{"demo.new": "1.0.0"})
    (tmp_path / "bin").mkdir()
    config = tmp_path / "bin/ansible-config"
    config.write_text("#!/bin/sh\necho 'Error reading config file' >&2\nexit 1\n")
    config.chmod(0o755)

    result = run_task(tmp_path, project)

    assert result.returncode == 1
    assert "Error reading config file" in result.stderr
    assert galaxy_calls(tmp_path) == []


def test_hk_step_runs_the_check_from_the_ansible_directory(rendered: Path) -> None:
    config = json.loads(
        subprocess.run(
            ["pkl", "eval", "--format", "json", ".config/hk/cubert.pkl"],  # noqa: S607
            cwd=rendered,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    step = config["steps"]["ansible-collections"]

    assert step["dir"] == "ansible"
    assert "requirements.yml" in step["glob"]
    assert textwrap.dedent(step["check"]).endswith('check_collections.py" .')
