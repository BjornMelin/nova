"""Typed helpers for worker-thread execution."""

from __future__ import annotations

from collections.abc import Callable

from anyio.abc import CapacityLimiter
from anyio.to_thread import (
    current_default_thread_limiter as anyio_current_default_thread_limiter,
)
from anyio.to_thread import (
    run_sync as anyio_run_sync,
)


async def run_sync[T](
    func: Callable[[], T],
    /,
    limiter: CapacityLimiter | None = None,
) -> T:
    """Run synchronous work in AnyIO's worker pool with preserved typing."""
    return await anyio_run_sync(func, limiter=limiter)


def current_default_thread_limiter() -> CapacityLimiter:
    """Return the AnyIO default worker-thread limiter."""
    return anyio_current_default_thread_limiter()
