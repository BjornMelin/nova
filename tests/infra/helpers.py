"""Shared test helpers for infrastructure contract tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]


def read_repo_file(rel_path: str) -> str:
    """Read a repository-relative file path."""
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Expected file to exist: {path}"
    return path.read_text(encoding="utf-8")


def load_repo_module(module_name: str, rel_path: str) -> ModuleType:
    """Load a repository module from a repository-relative file path."""
    module_path = REPO_ROOT / rel_path
    assert module_path.is_file(), (
        f"Expected module file to exist: {module_path}"
    )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
