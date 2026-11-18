"""Check that the ownership table, `_skip_if_exists` and `template/` agree.

copier.yml only records project-owned files, so the table alone separates
template-owned from merged files. This test cannot check that split.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("Template-owned", "Merged", "Project-owned")
# Copier writes and updates this file itself, so no row describes it.
COPIER_MANAGED = {".copier-answers.yml"}

CONDITIONAL = re.compile(r"\[% if [^%]+ %\](.*?)\[% endif %\]")


def rendered_path(template_path: str) -> str:
    """Return the path a project gets, with every optional part present."""
    parts = []
    for raw in template_path.removeprefix("template/").split("/"):
        part = raw.removesuffix(".jinja")
        part = part.replace("[[ _copier_conf.answers_file ]]", ".copier-answers.yml")
        part = part.replace("[[ opentofu_dir ]]", "<opentofu_dir>")
        part = part.replace("[[ ansible_dir ]]", "<ansible_dir>")
        parts.append(CONDITIONAL.sub(r"\1", part))
    return "/".join(parts)


def template_files() -> list[str]:
    """List the rendered path of each template file."""
    return sorted(
        rendered_path(path.relative_to(ROOT).as_posix())
        for path in (ROOT / "template").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )


def table_rows() -> dict[str, list[str]]:
    """Read the first table of File ownership in conventions.md, one list per kind."""
    rows: dict[str, list[str]] = {}
    for line in (ROOT / "template/docs/conventions.md").read_text().splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if line.startswith("|") and cells[0] in KINDS:
            rows[cells[0]] = re.findall(r"`([^`]+)`", cells[1])
    return rows


def skip_if_exists() -> list[str]:
    """Read `_skip_if_exists` from copier.yml. Copier needs no YAML parser here."""
    entries = []
    in_list = False
    for line in (ROOT / "copier.yml").read_text().splitlines():
        if line.startswith("_skip_if_exists:"):
            in_list = True
        elif in_list and (match := re.match(r'\s+- "(.+)"', line)):
            entry = match.group(1)
            for name in ("opentofu_dir", "ansible_dir"):
                entry = entry.replace(f"[[ {name} ]]", f"<{name}>")
            entries.append(entry)
        elif in_list and line.strip() and not line.lstrip().startswith("#"):
            break
    return entries


def matches(entry: str, path: str) -> bool:
    """A trailing slash makes the entry a directory prefix."""
    return path.startswith(entry) if entry.endswith("/") else path == entry


def kinds_of(path: str, rows: dict[str, list[str]]) -> list[str]:
    # An exact entry beats its directory: `.config/wt.toml` is merged inside `.config/`.
    exact = [kind for kind, entries in rows.items() if path in entries]
    if exact:
        return exact
    return [
        kind
        for kind, entries in rows.items()
        if any(matches(entry, path) for entry in entries)
    ]


def test_table_has_all_three_kinds() -> None:
    assert set(table_rows()) == set(KINDS)


def test_every_template_file_is_in_exactly_one_row() -> None:
    rows = table_rows()
    problems = []
    for path in template_files():
        if path in COPIER_MANAGED:
            continue
        found = kinds_of(path, rows)
        if len(found) != 1:
            problems.append(f"{path}: {found or 'no row'}")
    assert not problems, "\n".join(problems)


def test_project_owned_row_matches_skip_if_exists() -> None:
    files = [path for path in template_files() if path not in COPIER_MANAGED]
    rows = table_rows()
    skipped = set(skip_if_exists())
    # A row entry with no template file is a project-only path, such as `mise-tasks/`.
    in_row = {
        path
        for path in files
        if any(matches(entry, path) for entry in rows["Project-owned"])
    }
    assert in_row == skipped & set(files)
    stale = skipped - set(files)
    assert not stale, f"_skip_if_exists lists files that template/ lacks: {stale}"
