#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Fail when two mise task directories define a file task with the same name."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# mise's default task directories, in the order mise picks a winner (mise 2026.11).
# It runs only the first file task with a name, with no warning.
DIRS = ("mise/tasks", ".config/mise/tasks", ".mise/tasks", ".mise-tasks", "mise-tasks")


def task_name(relative: Path) -> str:
    """Return the task name that mise gives a file under a task directory."""
    parts = [*relative.parent.parts, relative.stem]
    if len(parts) > 1 and parts[-1] == "_default":
        parts.pop()
    return ":".join(parts)


def tasks(directory: Path) -> dict[str, Path]:
    """Map each file task name in a directory to its file, as mise loads them."""
    found: dict[str, Path] = {}
    # Shared task directories link into the template, so follow the links.
    for root, dirs, files in os.walk(directory, followlinks=True):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            path = Path(root, name)
            if not name.startswith(".") and os.access(path, os.X_OK):
                found.setdefault(task_name(path.relative_to(directory)), path)
    return found


def failures(root: Path) -> list[str]:
    """Return each file task that loses its name to a file in another directory."""
    winners: dict[str, Path] = {}
    found = []
    for directory in DIRS:
        for name, path in tasks(root / directory).items():
            if name in winners:
                found.append(
                    f"{path.relative_to(root)}: mise runs"
                    f" {winners[name].relative_to(root)} for {name}, not this file"
                )
            else:
                winners[name] = path
    return found


def main() -> int:
    """Print the losing files and how to override a shared task."""
    found = failures(Path())
    for failure in found:
        print(failure)
    if found:
        print(
            "Fix: rename or delete the file. To change a shared task, add"
            ' [tasks."<name>"] with its own run to mise.toml.'
        )
    return int(bool(found))


if __name__ == "__main__":
    sys.exit(main())
