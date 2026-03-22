"""Thin file-API assembly for canonical FastAPI exception handling."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from nova_runtime_support import (
    CanonicalErrorSpec,
    register_fastapi_exception_handlers,
)

from nova_file_api.errors import FileTransferError, internal_error
from nova_file_api.log_sanitization import sanitize_validation_errors


def register_exception_handlers(app: FastAPI) -> None:
    """Register canonical exception handlers for the file API runtime."""
    register_fastapi_exception_handlers(
        app,
        domain_error_type=FileTransferError,
        adapt_domain_error=_file_transfer_error_spec,
        validation_error_details=_validation_error_details,
        adapt_unhandled_error=_unhandled_error_spec,
        logger_name="errors",
    )


def _file_transfer_error_spec(exc: FileTransferError) -> CanonicalErrorSpec:
    """Adapt a file-API domain error into the shared transport shape."""
    return CanonicalErrorSpec(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        headers=exc.headers,
    )


def _validation_error_details(
    exc: RequestValidationError,
) -> dict[str, object]:
    """Sanitize FastAPI validation details for public responses."""
    return {"errors": sanitize_validation_errors(errors=exc.errors())}


def _unhandled_error_spec(_: Exception) -> CanonicalErrorSpec:
    """Return the canonical internal-error transport payload."""
    err = internal_error("unexpected internal error")
    return _file_transfer_error_spec(err)
