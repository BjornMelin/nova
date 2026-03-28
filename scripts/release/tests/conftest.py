"""Shared pytest fixtures for release-script tests."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Return a synthetic repository root under the test temp dir."""
    return tmp_path / "repo"


@pytest.fixture
def write_text() -> Callable[[Path, str], None]:
    """Write UTF-8 text after creating the parent directory."""

    def _write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    return _write


@pytest.fixture
def completed_process() -> Callable[..., subprocess.CompletedProcess[str]]:
    """Build a completed subprocess result with text IO defaults."""

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
