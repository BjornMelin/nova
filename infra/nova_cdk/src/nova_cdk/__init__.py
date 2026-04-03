"""Canonical CDK app for Nova serverless infrastructure."""

from __future__ import annotations

__all__ = [
    "NovaReleaseControlPlaneStack",
    "NovaReleaseSupportStack",
    "NovaRuntimeStack",
]


def __getattr__(name: str) -> object:
    """Resolve package exports lazily to avoid package import cycles."""
    if name == "NovaReleaseControlPlaneStack":
        from .release_control_stack import NovaReleaseControlPlaneStack

        return NovaReleaseControlPlaneStack
    if name == "NovaReleaseSupportStack":
        from .release_support_stack import NovaReleaseSupportStack

        return NovaReleaseSupportStack
    if name == "NovaRuntimeStack":
        from .runtime_stack import NovaRuntimeStack

        return NovaRuntimeStack
    raise AttributeError(name)
