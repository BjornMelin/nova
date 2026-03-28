"""Shared pytest fixtures for release-script tests."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Return an existing synthetic repository root.

    Args:
        tmp_path: Pytest-provided temporary directory for the test.

    Returns:
        Path to the created synthetic repository root.
    """
    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def write_text() -> Callable[[Path, str], None]:
    """Build a helper that writes UTF-8 text with parent directories created.

    Returns:
        Callable that writes UTF-8 text to a path after ensuring its parent
        directory exists.
    """

    def _write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    return _write


@pytest.fixture
def completed_process() -> Callable[..., subprocess.CompletedProcess[str]]:
    """Build subprocess results with text-mode defaults.

    Returns:
        Callable that constructs CompletedProcess[str] instances with default
        stdout and stderr values.
    """

    def _completed_process(
        *,
        args: list[str],
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    return _completed_process
