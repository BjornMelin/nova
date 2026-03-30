"""Canonical CDK app for Nova serverless infrastructure."""

from __future__ import annotations

__all__ = ["NovaRuntimeStack"]


def __getattr__(name: str) -> object:
    """Resolve package exports lazily to avoid package import cycles."""
    if name == "NovaRuntimeStack":
        from .runtime_stack import NovaRuntimeStack

        return NovaRuntimeStack
    raise AttributeError(name)
