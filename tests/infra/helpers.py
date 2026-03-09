"""Shared test helpers for infrastructure contract tests."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def read_repo_file(rel_path: str) -> str:
    """Read a repository-relative file path."""
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Expected file to exist: {path}"
    return path.read_text(encoding="utf-8")
