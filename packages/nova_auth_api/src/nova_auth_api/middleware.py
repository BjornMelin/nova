"""Request-context middleware for nova-auth-api."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from nova_runtime_support import (
    bind_request_id,
    finalize_request_id,
    request_id_from_request,
    unbind_request_id,
)
from starlette.responses import Response


def request_id(*, request: Request) -> str:
    """Return the active request id, creating one when missing."""
    current_request_id = request_id_from_request(request=request)
    if current_request_id is not None:
        return current_request_id
    return bind_request_id(request)


RequestIdDep = Annotated[str, Depends(request_id)]


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Inject request id into context and response headers."""
    current_request_id = bind_request_id(request)
    try:
        response = await call_next(request)
        return finalize_request_id(response, request_id=current_request_id)
    finally:
        unbind_request_id()
