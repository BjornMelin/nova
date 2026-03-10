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
    """
    Register exception handlers on a FastAPI application for file-transfer, request validation, and unhandled errors.
    
    Registers three handlers:
    - FileTransferError: returns a JSONResponse with the exception's status code, canonical error content built from the exception's code, message, details, and the request ID, and preserves the exception's headers.
    - RequestValidationError: returns a 422 JSONResponse with canonical error content (code "invalid_request", message "request validation failed") and details containing sanitized validation errors plus the request ID.
    - Exception (unhandled): logs the unhandled exception and returns a JSONResponse based on an internal error created for unexpected internal failures; the response uses the internal error's status, canonical content, and the request ID.
    
    Parameters:
        app (FastAPI): The FastAPI application to attach the exception handlers to.
    """

    @app.exception_handler(FileTransferError)
    async def file_transfer_error_handler(
        request: Request,
        exc: FileTransferError,
    ) -> JSONResponse:
        """
        Convert a FileTransferError into an HTTP JSON response.
        
        Parameters:
            request (Request): The incoming request; used to extract the request_id included in the response.
            exc (FileTransferError): The file transfer error containing status_code, code, message, details, and headers.
        
        Returns:
            JSONResponse: A response with the exception's status_code, canonicalized error content (including code, message, details, and request_id), and the exception's headers.
        """
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
        """
        Create a canonical HTTP 422 JSON response for a request validation error.
        
        Returns:
            JSONResponse: HTTP 422 response whose content is a canonical error object with code "invalid_request", message "request validation failed", details containing {"errors": <sanitized validation errors>}, and the request ID.
        """
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
        """
        Handle uncaught exceptions by logging the error and returning a canonical internal error response.
        
        Parameters:
            request (Request): The incoming HTTP request; its request ID is included in the response.
            exc (Exception): The unhandled exception that was raised.
        
        Returns:
            JSONResponse: A response with the internal error's status code and canonical error content containing the error `code`, `message`, `details`, and the `request_id`.
        """
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