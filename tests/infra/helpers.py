"""Shared test helpers for infrastructure contract tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]


def read_repo_file(rel_path: str) -> str:
    """Read a repository-relative file path.

    Args:
        rel_path: Repository-relative path to read.

    Returns:
        The file contents as UTF-8 text.
    """
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Expected file to exist: {path}"
    return path.read_text(encoding="utf-8")


def load_repo_module(module_name: str, rel_path: str) -> ModuleType:
    """Load a repository module from a repository-relative file path.

    Args:
        module_name: Repository module name to assign.
        rel_path: Repository-relative file path to load.

    Returns:
        The loaded module object.

    Raises:
        FileNotFoundError: If the path does not exist.
        ImportError: If the module cannot be loaded or executed.
    """
    module_path = REPO_ROOT / rel_path
    if not module_path.is_file():
        raise FileNotFoundError(f"Expected module file to exist: {module_path}")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec for: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def section_text(text: str, start_marker: str, end_marker: str) -> str:
    """Return the text between two required section markers."""
    start = text.find(start_marker)
    assert start != -1, f"Missing section marker: {start_marker}"
    end = text.find(end_marker, start)
    assert end != -1, f"Missing section terminator: {end_marker}"
    return text[start:end]
