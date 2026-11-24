"""Test that the template seeds no tool versions, and that the hk package matches hk."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support import load_script

check_versions = load_script("scripts/check_versions.py")


def failures_in(tmp_path: Path, files: dict[str, str]) -> list[str]:
    """Run the check on a minimal repository, with `files` added or replaced."""
    base = {
        "mise.toml": '[tools]\nhk = "2.11.1"\n',
        "template/mise.toml.jinja": '[tools]\nhk = "latest"\n',
        "template/.config/hk/base.pkl": "",
        "template/.config/hk/cubert.pkl.jinja": "",
        "hk.pkl": "",
        "template/.config/mise/required-tools.jinja": "hk>=2.11.1\n",
    }
    for name, text in (base | files).items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    return check_versions.failures(tmp_path)


def test_template_tools_reads_every_feature_block() -> None:
    text = (
        '[tools]\nhk = "1"\n[% if python %]\nruff = "2"\n[% endif %]\n'
        '\n[tasks.x]\nrun = "y"\n'
    )
    assert check_versions.template_tools(text) == {"hk": "1", "ruff": "2"}


def test_minimal_repository_passes(tmp_path: Path) -> None:
    assert failures_in(tmp_path, {}) == []


def test_exact_seed_fails(tmp_path: Path) -> None:
    files = {
        "template/mise.toml.jinja": (
            '[tools]\nhk = "latest"\njq = "1.8.2"\nnode = "lts"\n'
        ),
        "template/.config/mise/required-tools.jinja": "hk>=2.11.1\njq\nnode\n",
    }
    assert len(failures_in(tmp_path, files)) == 1


def test_required_tools_read_every_feature_block() -> None:
    text = "# Comment\nhk\n[% if python %]\nruff\n[% endif %]\n"
    assert check_versions.required_tools(text) == {"hk", "ruff"}


def test_seeded_tool_must_be_required(tmp_path: Path) -> None:
    files = {"template/mise.toml.jinja": '[tools]\nhk = "latest"\njq = "latest"\n'}
    assert len(failures_in(tmp_path, files)) == 1


def test_hk_package_must_match_hk(tmp_path: Path) -> None:
    url = "package://github.com/jdx/hk/releases/download/v2.10.0/hk@2.10.0#/Config.pkl"
    assert len(failures_in(tmp_path, {"template/.config/hk/base.pkl": url})) == 1


@pytest.mark.parametrize(
    "name", ["ci.yml.jinja", "[% if backup %]backup.yml[% endif %].jinja"]
)
def test_jinja_workflow_must_match_bumped_action(tmp_path: Path, name: str) -> None:
    files = {
        "template/.github/workflows/ci.yml": '- uses: "actions/checkout@v7.0.2"\n',
        f"template/.github/workflows/{name}": (
            '- uses: "actions/checkout@v7.0.1"\n'
            '- uses: "./.github/actions/setup-mise"\n'
        ),
    }
    assert len(failures_in(tmp_path, files)) == 1


def test_jinja_workflow_ignores_cubert_workflow_tags(
    tmp_path: Path,
) -> None:
    files = {
        ".github/workflows/ci.yml": '- uses: "actions/upload-artifact@v7.0.2"\n',
        "template/.github/workflows/ci.yml.jinja": (
            '- uses: "actions/upload-artifact@v7.0.1"\n'
        ),
    }
    assert failures_in(tmp_path, files) == []


def test_jinja_workflow_ignores_composite_action_sha_pins(tmp_path: Path) -> None:
    files = {
        "template/.github/actions/demo/action.yml": (
            '- uses: "actions/cache@55cc834" # v6.1.0\n'
        ),
        "template/.github/workflows/ci.yml.jinja": '- uses: "actions/cache@v6.1.0"\n',
    }
    assert failures_in(tmp_path, files) == []


@pytest.mark.parametrize("name", ["ci.yml", "ci.yml.jinja"])
def test_template_workflow_must_name_an_action_tag(tmp_path: Path, name: str) -> None:
    sha = "55cc8345863c7cc4c66a329aec7e433d2d1c52a9"
    files = {f"template/.github/workflows/{name}": f'- uses: "actions/cache@{sha}"\n'}
    assert len(failures_in(tmp_path, files)) == 1


def test_template_workflow_may_pin_a_reusable_workflow_to_a_sha(tmp_path: Path) -> None:
    sha = "55cc8345863c7cc4c66a329aec7e433d2d1c52a9"
    uses = f'uses: "octo/repo/.github/workflows/ci.yml@{sha}"\n'
    files = {"template/.github/workflows/ci.yml": uses}
    assert failures_in(tmp_path, files) == []


def test_required_minimum_key_drops_tool_options() -> None:
    minimums = check_versions.required_minimums("github:a/b[bin=b]>=0.5.1\n")
    assert minimums == {"github:a/b": "0.5.1"}


def test_repository_passes() -> None:
    assert check_versions.failures(Path()) == []


def test_required_hk_minimum_must_match_the_hk_tool(tmp_path: Path) -> None:
    files = {"template/.config/mise/required-tools.jinja": "hk>=2.10.0\n"}
    assert len(failures_in(tmp_path, files)) == 1


def test_required_minimum_does_not_change_the_tool_name(tmp_path: Path) -> None:
    assert failures_in(tmp_path, {}) == []


def test_inline_tool_options_keep_the_seeded_version_visible() -> None:
    text = '[tools]\n"pypi:copier" = { version = "latest", python = "3.14" }\n'
    assert check_versions.template_tools(text) == {"pypi:copier": "latest"}


def test_inline_tool_options_do_not_hide_an_exact_seed(tmp_path: Path) -> None:
    files = {
        "template/mise.toml.jinja": (
            '[tools]\nhk = { version = "2.11.1", python = "3.14" }\n'
        ),
    }
    assert len(failures_in(tmp_path, files)) == 1
