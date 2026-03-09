"""Shared FastAPI request-id and canonical error-envelope helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import structlog
from fastapi import Request
from starlette.responses import Response


def bind_request_id(request: Request) -> str:
    """Bind the request identifier to request state and structlog context.

    Args:
        request: Incoming FastAPI/Starlette request object.

    Returns:
        str: Request identifier bound to state and logging context.
    """
    request_id = request.headers.get("X-Request-Id") or uuid4().hex
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=request_id)
    return request_id


def finalize_request_id(response: Response, *, request_id: str) -> Response:
    """Attach the request identifier to the outgoing response headers.

    Args:
        response: Outgoing response object to mutate.
        request_id: Request identifier to expose via ``X-Request-Id`` header.

    Returns:
        Response: The same response object with request-id header applied.
    """
    response.headers["X-Request-Id"] = request_id
    return response


def unbind_request_id() -> None:
    """Remove the request identifier from structlog context vars.

    Returns:
        None.
    """
    structlog.contextvars.unbind_contextvars("request_id")


def request_id_from_request(*, request: Request) -> str | None:
    """Read the normalized request identifier from request state or headers.

    Args:
        request: Incoming request object with state and headers.

    Returns:
        str | None: Normalized request id when available, otherwise ``None``.
    """
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    value = request.headers.get("X-Request-Id")
    if isinstance(value, str) and value:
        return value
    return None


def canonical_error_content(
    *,
    code: str,
    message: str,
    details: Mapping[str, Any] | None = None,
    request_id: str | None,
) -> dict[str, Any]:
    """Build the canonical Nova error envelope payload as a JSON-ready dict.

    Args:
        code: Canonical machine-readable error code.
        message: Human-readable error message.
        details: Optional structured detail payload.
        request_id: Request identifier to include in the envelope.

    Returns:
        dict[str, Any]: Canonical error payload with top-level ``error`` key.
    """
    return {
        "error": {
            "code": code,
            "message": message,
            "details": dict(details or {}),
            "request_id": request_id,
        }
    }
