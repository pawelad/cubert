"""Load a script that has no package as a module, so tests can call its functions."""

from __future__ import annotations

import importlib.util
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
