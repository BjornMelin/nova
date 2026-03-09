"""HTTP middleware components."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter

import structlog
from fastapi import Request
from nova_runtime_support import (
    bind_request_id,
    finalize_request_id,
    unbind_request_id,
)
from starlette.responses import Response


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Inject request ID into context and response headers."""
    started = perf_counter()
    request_id = bind_request_id(request)
    logger = structlog.get_logger("http")
    auth_mode = _auth_mode_value(request=request)
    path = request.url.path
    method = request.method

    try:
        response = await call_next(request)
    except Exception:
        latency_ms = (perf_counter() - started) * 1000.0
        logger.exception(
            "request_completed",
            method=method,
            path=path,
            status_code=500,
            outcome="error",
            latency_ms=round(latency_ms, 3),
            auth_mode=auth_mode,
        )
        unbind_request_id()
        raise

    finalize_request_id(response, request_id=request_id)
    latency_ms = (perf_counter() - started) * 1000.0
    status_code = response.status_code
    outcome = "ok" if status_code < 400 else "error"
    logger.info(
        "request_completed",
        method=method,
        path=path,
        status_code=status_code,
        outcome=outcome,
        latency_ms=round(latency_ms, 3),
        auth_mode=auth_mode,
    )
    unbind_request_id()
    return response


def _auth_mode_value(*, request: Request) -> str | None:
    settings = getattr(request.app.state, "settings", None)
    value = getattr(settings, "auth_mode", None)
    if value is None:
        return None
    return str(value)
