"""AWS SDK runtime helpers shared across Nova packages."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def new_aioboto3_session() -> Any:
    """Return a lazily imported aioboto3 session."""
    return import_module("aioboto3").Session()
