"""Exception handlers for nova-auth-api."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from nova_runtime_support import canonical_error_content

from nova_auth_api.errors import AuthApiError, internal_error
from nova_auth_api.middleware import request_id

SENSITIVE_VALIDATION_FIELDS = {"access_token", "authorization", "token"}


def register_exception_handlers(app: FastAPI) -> None:
    """Register canonical exception handlers on the FastAPI app."""

    @app.exception_handler(AuthApiError)
    async def auth_error_handler(
        request: Request,
        exc: AuthApiError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=canonical_error_content(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=request_id(request=request),
            ),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=canonical_error_content(
                code="invalid_request",
                message="request validation failed",
                details={
                    "errors": sanitize_validation_errors(errors=exc.errors())
                },
                request_id=request_id(request=request),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        log = structlog.get_logger("errors")
        log.exception(
            "unhandled_exception",
            error_type=type(exc).__name__,
            request_id=request_id(request=request),
        )
        err = internal_error("unexpected internal error")
        return JSONResponse(
            status_code=err.status_code,
            content=canonical_error_content(
                code=err.code,
                message=err.message,
                details=err.details,
                request_id=request_id(request=request),
            ),
        )


def sanitize_validation_errors(
    *,
    errors: Sequence[Any],
) -> list[dict[str, Any]]:
    """Redact sensitive validation inputs before returning them to callers."""
    output: list[dict[str, Any]] = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        sanitized = dict(error)
        location = sanitized.get("loc", ())
        if validation_loc_is_sensitive(loc=location) and "input" in sanitized:
            sanitized["input"] = "[REDACTED]"
        output.append(sanitized)
    return output


def validation_loc_is_sensitive(*, loc: object) -> bool:
    """Return whether a validation location references a sensitive field."""
    if not isinstance(loc, (tuple, list)):
        return False
    for value in loc:
        if (
            isinstance(value, str)
            and value.lower() in SENSITIVE_VALIDATION_FIELDS
        ):
            return True
    return False
