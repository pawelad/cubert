"""Check that the hk.pkl snippets in docs/conventions.md evaluate in a project."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

import pytest

from tests.support import project_env, render_template, run

pytestmark = pytest.mark.skipif(
    shutil.which("copier") is None
    or shutil.which("pkl") is None
    or shutil.which("hk") is None,
    reason="needs copier, pkl and hk on PATH",
)

# hk.pkl.jinja renders the amends line last, so a snippet appends below it.
HEADER = 'amends ".config/hk/cubert.pkl"\n'
# The `hooks["check"]` snippet turns off a project step, so the test adds one.
VECTOR_STEP = 'steps { ["vector"] = new Step { check = "true" } }\n'
FRAGMENT_LOOP = "[name] { exclude = super.exclude + frozenPaths }"


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render_template(tmp_path_factory.mktemp("render"), typescript="true")


@pytest.fixture(scope="module")
def snippets(project: Path) -> list[str]:
    """Return each pkl block of the rendered conventions.md, in document order."""
    text = (project / "docs/conventions.md").read_text()
    blocks = re.findall(r"^( *)```pkl\n(.*?)^\1```", text, re.MULTILINE | re.DOTALL)
    return [textwrap.dedent(body) for _, body in blocks]


def evaluate(project: Path, body: str) -> dict[str, Any]:
    """Write `body` as the project hk.pkl, validate it with hk and return its JSON."""
    (project / "hk.pkl").write_text(HEADER + body)
    run(["hk", "validate"], project)
    config: dict[str, Any] = json.loads(
        run(["pkl", "eval", "--format", "json", "hk.pkl"], project)
    )
    return config


def snippet(snippets: list[str], marker: str) -> str:
    [found] = [s for s in snippets if marker in s]
    return found


def test_depends_snippet_runs_expo_types_before_tsc(
    project: Path, snippets: list[str]
) -> None:
    config = evaluate(project, snippet(snippets, '["expo-types"]'))

    assert config["steps"]["tsc"]["depends"] == ["expo-types"]


def test_generator_snippet_gives_the_step_a_fixer_that_runs_before_biome(
    project: Path, snippets: list[str]
) -> None:
    config = evaluate(project, snippet(snippets, '["api-types"]'))

    step = config["steps"]["api-types"]
    assert step["fix"] == step["check"]
    assert config["steps"]["biome"]["depends"] == ["api-types"]


def test_hook_snippet_keeps_a_step_out_of_the_check_hook(
    project: Path, snippets: list[str]
) -> None:
    config = evaluate(project, VECTOR_STEP + snippet(snippets, 'hooks {\n  ["check"]'))

    assert config["hooks"]["check"]["steps"]["vector"]["condition"] == "false"


def test_frozen_loop_snippet_excludes_the_paths_from_shared_steps(
    project: Path, snippets: list[str]
) -> None:
    config = evaluate(project, snippet(snippets, "for (name, step in shared.steps)"))

    assert "docs/legacy/**" in config["steps"]["typos"]["exclude"]
    assert "docs/legacy/**" not in config["steps"]["dprint"].get("exclude", [])


def test_hk_skips_the_frozen_loop_paths(project: Path, snippets: list[str]) -> None:
    # hk evaluates with pklr, which can differ from `pkl eval` and skip a loop silently.
    evaluate(project, snippet(snippets, "for (name, step in shared.steps)"))
    run(["git", "init", "--quiet"], project)
    (project / "docs/legacy").mkdir(parents=True, exist_ok=True)
    (project / "docs/legacy/old.md").write_text("colour\n")
    (project / "new.md").write_text("colour\n")

    result = subprocess.run(
        ["hk", "check", "--step", "no-british-english", "docs/legacy/old.md", "new.md"],  # noqa: S607
        cwd=project,
        env=project_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert "new.md:1:colour" in output
    assert "docs/legacy/old.md" not in output


def test_glob_snippet_checks_whole_files_of_a_type(
    project: Path, snippets: list[str]
) -> None:
    config = evaluate(project, snippet(snippets, '["no-em-dashes"] { glob'))

    for full in ("no-em-dashes", "no-british-english"):
        assert "*.j2" in config["steps"][full]["glob"]
        twin = config["hooks"]["check"]["steps"][f"{full}-comments"]
        assert "*.j2" in twin["exclude"]
        assert "**/vendor/**" in twin["exclude"]


def loop_with_user_text(snippets: list[str]) -> str:
    """Return the frozen loop with the glob fragment in it, as the text describes."""
    loop = snippet(snippets, "for (name, step in shared.steps)")
    fragment = snippet(snippets, "[name] {\n  exclude = super.exclude + frozenPaths\n")
    assert FRAGMENT_LOOP in loop
    body = loop.replace(FRAGMENT_LOOP, textwrap.indent(fragment, "      ").strip())
    # The text asks for the glob snippet's userText next to frozenPaths.
    glob = snippet(snippets, '["no-em-dashes"] { glob')
    [user_text] = [line for line in glob.splitlines() if "local userText" in line]
    return body.replace("\nsteps {", f"\n{user_text}\n\nsteps {{", 1)


def test_loop_fragment_sets_the_glob_inside_the_frozen_loop(
    project: Path, snippets: list[str]
) -> None:
    config = evaluate(project, loop_with_user_text(snippets))

    steps = config["steps"]
    check = config["hooks"]["check"]["steps"]
    assert "*.j2" in steps["no-em-dashes"]["glob"]
    assert "docs/legacy/**" in steps["no-em-dashes"]["exclude"]
    assert "*.j2" in check["no-em-dashes-comments"]["exclude"]
    assert "docs/legacy/**" in check["no-em-dashes-comments"]["exclude"]
    assert "*.j2" not in check["no-emojis-comments"]["exclude"]


def test_check_prints_a_comment_error_in_a_widened_glob_once(
    project: Path, snippets: list[str]
) -> None:
    # mise run check passes --no-fail-fast, so a matching twin would report it too.
    evaluate(project, loop_with_user_text(snippets))
    run(["git", "init", "--quiet"], project)
    (project / "card.j2").write_text("{# One \u2014 two. #}\n-- One \u2014 two.\n")

    result = subprocess.run(
        [  # noqa: S607
            "hk",
            "check",
            "--no-fail-fast",
            "--step",
            "no-em-dashes",
            "--step",
            "no-em-dashes-comments",
            "card.j2",
        ],
        cwd=project,
        env=project_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    # hk marks each failed step with a cross and an en dash.
    failed = re.findall(r"^\u2717 (\S+) \u2013 ERROR", output, re.MULTILINE)
    assert failed == ["no-em-dashes"], output


def test_change_step_snippet_adds_to_the_shared_excludes(project: Path) -> None:
    text = (project / "docs/conventions.md").read_text()
    [body] = re.findall(r"Change a shared step:\s*`(steps \{.*?\} \})`", text)

    config = evaluate(project, body + "\n")

    exclude = config["steps"]["typos"]["exclude"]
    assert "gen/**" in exclude
    assert "**/vendor/**" in exclude


def test_hk_keeps_the_shared_frozen_paths_beside_a_project_local_named_frozen(
    project: Path,
) -> None:
    # hk's evaluator resolved base.pkl's import by name in the project's scope.
    body = (
        'local frozen = List("db/**")\n'
        'steps { ["typos"] { exclude = super.exclude + frozen } }\n'
    )

    config = evaluate(project, body)

    assert {"db/**", "**/vendor/**"} <= set(config["steps"]["typos"]["exclude"])
