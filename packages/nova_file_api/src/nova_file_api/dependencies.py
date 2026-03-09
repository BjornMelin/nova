"""FastAPI dependency helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Annotated, cast

import anyio
from anyio.abc import CapacityLimiter
from fastapi import Depends, Request

from nova_file_api.container import AppContainer
from nova_file_api.models import Principal

_APPLICATION_CONTAINER_NOT_INITIALIZED = (
    "application container is not initialized"
)
_APPLICATION_BLOCKING_IO_LIMITER_NOT_INITIALIZED = (
    "application blocking I/O limiter is not initialized"
)
BLOCKING_IO_LIMITER_STATE_KEY = "blocking_io_thread_limiter"


def get_container(request: Request) -> AppContainer:
    """Return dependency container from app state."""
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, AppContainer):
        raise TypeError(_APPLICATION_CONTAINER_NOT_INITIALIZED)
    return container


def get_request_id(request: Request) -> str | None:
    """Return request-id value from middleware state."""
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str):
        return value
    return None


def get_blocking_io_limiter(request: Request) -> CapacityLimiter:
    """Return the app-scoped limiter for blocking runtime work."""
    limiter = getattr(request.app.state, BLOCKING_IO_LIMITER_STATE_KEY, None)
    if limiter is None:
        raise TypeError(_APPLICATION_BLOCKING_IO_LIMITER_NOT_INITIALIZED)
    return cast(CapacityLimiter, limiter)


@dataclass(slots=True)
class RequestContext:
    """Bundle request-scoped dependencies shared by route handlers."""

    request: Request
    container: AppContainer
    blocking_io_limiter: CapacityLimiter

    async def authenticate(self, *, session_id: str | None) -> Principal:
        """Authenticate the current caller for the request."""
        return await self.container.authenticator.authenticate(
            request=self.request,
            session_id=session_id,
        )

    async def run_blocking[**P, R](
        self,
        fn: Callable[P, R],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Run blocking work via the runtime-specific limiter."""
        return await anyio.to_thread.run_sync(
            partial(fn, *args, **kwargs),
            limiter=self.blocking_io_limiter,
        )


def get_request_context(
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
    blocking_io_limiter: Annotated[
        CapacityLimiter, Depends(get_blocking_io_limiter)
    ],
) -> RequestContext:
    """Return a request-scoped runtime context for handlers."""
    return RequestContext(
        request=request,
        container=container,
        blocking_io_limiter=blocking_io_limiter,
    )


ContainerDep = Annotated[AppContainer, Depends(get_container)]
RequestContextDep = Annotated[RequestContext, Depends(get_request_context)]
