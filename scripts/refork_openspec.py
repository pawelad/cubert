#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""Turn a fresh `openspec schema fork spec-driven changes-only` into our schema.

Edits the text, not parsed YAML, so the upstream wording and layout stay reviewable
in the diff. Each edit must match once, so an upstream change fails loudly.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DESCRIPTION = "description: 'Change proposals without specs: proposal, design, tasks'"


def _replace(text: str, pattern: str, replacement: str, *, name: str) -> str:
    new_text, count = re.subn(
        pattern, replacement, text, count=1, flags=re.DOTALL | re.MULTILINE
    )
    if count != 1:
        msg = f"edit {name!r} did not match: upstream changed, update this script"
        raise SystemExit(msg)
    return new_text


def transform_schema(text: str) -> str:
    """Drop the specs artifact and its references from the forked schema."""
    text = _replace(text, r"^description: [^\n]*$", DESCRIPTION, name="description")
    text = _replace(
        text,
        r"^      - \*\*Capabilities\*\*:.*?(?=^      - \*\*Impact\*\*)",
        "",
        name="proposal capabilities section",
    )
    text = _replace(
        text,
        r"^      IMPORTANT: The Capabilities section.*?(?=^      Keep it concise)",
        "",
        name="proposal capabilities guidance",
    )
    text = _replace(
        text,
        r"specs, design, and tasks all build on this\.",
        "design and tasks build on this.",
        name="proposal foundation line",
    )
    text = _replace(
        text,
        r"^  - id: specs\n.*?(?=^  - id: design)",
        "",
        name="specs artifact",
    )
    text = _replace(
        text,
        r" Reference the\n(\s+)proposal for motivation and, once written,"
        r" the specs for requirements -\n"
        r"\s+if a section would only restate them, point to them instead\.",
        " Reference the\n\\1proposal for motivation instead of restating it.",
        name="design specs reference",
    )
    text = _replace(
        text,
        r"changing the specs, the approach, or the task breakdown\.",
        "changing the approach or the task breakdown.",
        name="design open questions",
    )
    text = _replace(
        text,
        r"would change the specs, the chosen approach, or\n",
        "would change the chosen approach or\n",
        name="design open questions guidance",
    )
    text = _replace(
        text,
        r"Reference specs for what needs to be built, design for how to build it\.",
        "Reference the proposal for what to build and design for how to build it.",
        name="tasks reference line",
    )
    return _replace(
        text,
        r"^    requires:\n      - specs\n      - design\n",
        "    requires:\n      - design\n",
        name="tasks requires",
    )


def transform_proposal_template(text: str) -> str:
    """Drop the Capabilities section, which only the specs artifact uses."""
    return _replace(
        text,
        r"^## Capabilities\n.*?(?=^## )",
        "",
        name="proposal template capabilities",
    )


def main(schema_dir: str) -> int:
    """Rewrite the forked schema in `schema_dir` in place."""
    root = Path(schema_dir)
    schema = root / "schema.yaml"
    schema.write_text(transform_schema(schema.read_text()))
    proposal = root / "templates" / "proposal.md"
    proposal.write_text(transform_proposal_template(proposal.read_text()))
    (root / "templates" / "spec.md").unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
