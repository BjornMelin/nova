"""Exception handler registration for the file API application."""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from nova_runtime_support import (
    canonical_error_content,
    request_id_from_request,
)

from nova_file_api.errors import FileTransferError, internal_error
from nova_file_api.log_sanitization import sanitize_validation_errors


def register_exception_handlers(app: FastAPI) -> None:
    """Register canonical exception handlers for runtime errors."""

    @app.exception_handler(FileTransferError)
    async def file_transfer_error_handler(
        request: Request,
        exc: FileTransferError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=canonical_error_content(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=request_id_from_request(request=request),
            ),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        validation_errors = sanitize_validation_errors(errors=exc.errors())
        return JSONResponse(
            status_code=422,
            content=canonical_error_content(
                code="invalid_request",
                message="request validation failed",
                details={"errors": validation_errors},
                request_id=request_id_from_request(request=request),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        structlog.get_logger("errors").exception(
            "unhandled_exception",
            error_type=type(exc).__name__,
        )
        err = internal_error("unexpected internal error")
        return JSONResponse(
            status_code=err.status_code,
            content=canonical_error_content(
                code=err.code,
                message=err.message,
                details=err.details,
                request_id=request_id_from_request(request=request),
            ),
        )
