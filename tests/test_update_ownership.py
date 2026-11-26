"""Check what `copier update` does to each kind of file, as conventions.md states.

The test renders the working tree as release 1, edits the project, changes the
template to release 2 and updates. Copier's own rules decide the outcome, so this
test pins them for the Copier version that cubert requires.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.support import (
    commit_all,
    copy_project,
    project_env,
    run,
    snapshot_template,
)

pytestmark = pytest.mark.skipif(
    shutil.which("copier") is None, reason="needs copier on PATH"
)


def prepend(path: Path, line: str) -> None:
    path.write_text(f"{line}\n{path.read_text()}")


@pytest.fixture(scope="module")
def updated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("ownership")
    source = base / "cubert"
    source.mkdir()
    release1 = snapshot_template(source)
    project = base / "project"
    # TypeScript adds `.config/biome.json`, which shares a name with a project file.
    copy_project(source, release1, project, typescript="true")
    run(["git", "-c", "init.defaultBranch=main", "init", "--quiet"], project)
    commit_all(project, "chore: render release 1")

    # Release 2 edits a template-owned and a project-owned file, and removes another.
    template = source / "template"
    prepend(template / ".config/yamllint.yaml", "# release 2")
    prepend(template / "CONTRIBUTING.md", "<!-- release 2 -->")
    (template / ".shellcheckrc").unlink()
    for name in ("[% if typescript %]biome.json[% endif %]", "dprint.json"):
        path = template / ".config" / name
        path.write_text(path.read_text().replace("{", '{\n  "$release": 2,', 1))
    release2 = commit_all(source, "chore: release 2")

    # The project edits the same spots, deletes two files and edits the removed one.
    prepend(project / ".config/yamllint.yaml", "# local edit")
    prepend(project / "CONTRIBUTING.md", "<!-- local edit -->")
    (project / ".shellcheckrc").write_text("# local edit\n")
    (project / ".editorconfig").unlink()
    (project / "LICENSE").unlink()
    commit_all(project, "chore: edit the project")

    command = ["copier", "update", "--quiet", "--defaults", "--skip-answered"]
    run([*command, "--vcs-ref", release2], project, project_env())
    return project


def test_edit_to_a_template_owned_file_conflicts_with_the_template(
    updated: Path,
) -> None:
    text = (updated / ".config/yamllint.yaml").read_text()

    assert "<<<<<<<" in text
    assert "# release 2" in text
    assert "# local edit" in text


@pytest.mark.parametrize("name", ["biome.json", "dprint.json"])
def test_template_change_reaches_config_file_named_like_a_project_owned_file(
    updated: Path, name: str
) -> None:
    assert '"$release": 2' in (updated / ".config" / name).read_text()


def test_edit_to_a_project_owned_file_stays_and_ignores_the_template(
    updated: Path,
) -> None:
    text = (updated / "CONTRIBUTING.md").read_text()

    assert text.startswith("<!-- local edit -->")
    assert "release 2" not in text


def test_deleted_project_owned_file_is_created_again(updated: Path) -> None:
    assert (updated / "LICENSE").is_file()


def test_deleted_template_owned_file_stays_deleted(updated: Path) -> None:
    assert not (updated / ".editorconfig").exists()


def test_file_that_the_template_removes_is_deleted_despite_a_local_edit(
    updated: Path,
) -> None:
    assert not (updated / ".shellcheckrc").exists()
