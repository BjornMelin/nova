"""Repo-wide pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Pin async test execution to asyncio for the whole repo."""
    return "asyncio"
