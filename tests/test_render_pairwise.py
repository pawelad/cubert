"""Check that the pairwise renders cover every pair of answer values."""

from __future__ import annotations

import itertools
import re

from tests.support import ROOT

# python, docker, opentofu, ansible, changelog, typescript, then openspec.
NAME = re.compile(
    r"^p([01])d([01])t([01])a([01])c([01])s([01])_(none|changes-only|spec-driven)$"
)
VALUES = [("0", "1")] * 6 + [("none", "changes-only", "spec-driven")]


def pairwise_names() -> list[str]:
    text = (ROOT / "scripts/render_pairwise.txt").read_text()
    return [line for line in text.splitlines() if line and not line.startswith("#")]


def test_each_name_is_a_render_combination() -> None:
    names = pairwise_names()

    assert names
    assert [name for name in names if not NAME.match(name)] == []
    assert len(set(names)) == len(names)


def test_names_cover_every_pair_of_answer_values() -> None:
    rows = [NAME.match(name).groups() for name in pairwise_names()]  # type: ignore[union-attr]
    missing = [
        (i, a, j, b)
        for i, j in itertools.combinations(range(len(VALUES)), 2)
        for a in VALUES[i]
        for b in VALUES[j]
        if not any(row[i] == a and row[j] == b for row in rows)
    ]

    assert missing == []


def test_opentofu_renders_cover_each_credential_store_and_backup_shape() -> None:
    # Mirrors scripts/render.sh: docker off adds the state backup, and ansible, then
    # changelog, pick the credential store.
    shapes = set()
    for name in pairwise_names():
        _, d, t, a, c, _, _ = NAME.match(name).groups()  # type: ignore[union-attr]
        if t == "1":
            store = "age" if a == "1" else "proton-pass" if c == "1" else "none"
            shapes.add((store, d == "0"))

    assert {store for store, _ in shapes} == {"none", "proton-pass", "age"}
    assert {("none", True), ("none", False)} <= shapes
    assert {backup for store, backup in shapes if store != "none"} == {True, False}
