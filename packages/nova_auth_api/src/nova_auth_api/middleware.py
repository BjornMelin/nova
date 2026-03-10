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
    """
    Return the request identifier associated with the given HTTP request.
    
    If the request already has an identifier, it is returned; otherwise a new identifier is bound to the request and returned.
    
    Returns:
        str: The request identifier associated with the request.
    """
    current_request_id = request_id_from_request(request=request)
    if current_request_id is not None:
        return current_request_id
    return bind_request_id(request)


RequestIdDep = Annotated[str, Depends(request_id)]


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """
    Bind the request's ID into the runtime context, invoke the next handler, finalize the response with that ID, and always clean up the context.
    
    Parameters:
        request (Request): The incoming HTTP request.
        call_next (Callable[[Request], Awaitable[Response]]): Callable that processes the request and returns a Response.
    
    Returns:
        Response: The response returned by the next handler, with the request ID attached or propagated.
    
    Notes:
        The request ID is unbound from the runtime context after the response is finalized, regardless of success or error.
    """
    current_request_id = bind_request_id(request)
    try:
        response = await call_next(request)
        return finalize_request_id(response, request_id=current_request_id)
    finally:
        unbind_request_id()