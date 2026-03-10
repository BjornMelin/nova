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
        """
        Handle an AuthApiError by returning a canonical JSON error response.
        
        Parameters:
            request (Request): Incoming request used to extract the request_id.
            exc (AuthApiError): Error containing code, message, details, status_code, and headers to include in the response.
        
        Returns:
            JSONResponse: Response whose body is the canonical error content (code, message, details, request_id) and whose status code and headers are taken from `exc`.
        """
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
        """
        Handle request validation errors and return a canonical 422 error response.
        
        This constructs a JSONResponse with a canonical error body where validation errors
        from `exc` are sanitized to redact sensitive input values and included under
        `details["errors"]`. The response also includes a `request_id` extracted from
        `request`.
        
        Parameters:
            request (Request): Incoming request used to obtain the request identifier.
            exc (RequestValidationError): Validation error containing the list of validation issues.
        
        Returns:
            JSONResponse: HTTP 422 response whose body contains:
                - `code`: "invalid_request"
                - `message`: "request validation failed"
                - `details.errors`: sanitized list of validation error objects
                - `request_id`: identifier for the request
        """
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
        """
        Handle uncaught exceptions by logging the error and returning a canonical internal error response.
        
        Returns:
            JSONResponse: A JSONResponse containing the canonical internal error payload and the internal error's status code.
        """
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
    """
    Sanitize a sequence of validation error objects by redacting sensitive input values.
    
    Parameters:
        errors (Sequence[Any]): Sequence of validation error objects (typically dict-like items with keys such as `"loc"` and `"input"`).
    
    Returns:
        list[dict[str, Any]]: A list of validation error dictionaries where any `"input"` value whose location is considered sensitive is replaced with `"[REDACTED]"`.
    """
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
    """
    Determine whether a validation location refers to a sensitive field.
    
    Parameters:
    	loc (object): The validation location (typically a tuple or list of path elements) produced by a validation error.
    
    Returns:
    	True if `loc` is a tuple or list containing a string element that, case-insensitively, matches one of the configured sensitive field names; False otherwise.
    """
    if not isinstance(loc, (tuple, list)):
        return False
    for value in loc:
        if (
            isinstance(value, str)
            and value.lower() in SENSITIVE_VALIDATION_FIELDS
        ):
            return True
    return False
