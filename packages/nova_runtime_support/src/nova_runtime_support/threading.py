"""Typed helpers for worker-thread execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from anyio.abc import CapacityLimiter
from anyio.to_thread import (
    current_default_thread_limiter as anyio_current_default_thread_limiter,
    run_sync as anyio_run_sync,
)

T = TypeVar("T")


async def run_sync(
    func: Callable[[], T],
    /,
    limiter: CapacityLimiter | None = None,
) -> T:
    """Run synchronous work in AnyIO's worker pool with preserved typing.

    Args:
        func: Synchronous callable to execute in the worker-thread pool.
        limiter: Optional AnyIO capacity limiter for worker-thread concurrency.

    Returns:
        The value returned by ``func``.

    Raises:
        Exception: Propagates exceptions raised by ``func``.
    """
    return await anyio_run_sync(func, limiter=limiter)


def current_default_thread_limiter() -> CapacityLimiter:
    """Return the AnyIO default worker-thread limiter.

    Returns:
        The process-wide default ``CapacityLimiter`` for AnyIO worker threads.
    """
    return anyio_current_default_thread_limiter()
