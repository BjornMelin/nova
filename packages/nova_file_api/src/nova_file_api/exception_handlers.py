"""Thin file-API assembly for canonical FastAPI exception handling."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from nova_file_api.errors import FileTransferError, internal_error
from nova_file_api.log_sanitization import sanitize_validation_errors
from nova_runtime_support import (
    CanonicalErrorSpec,
    canonical_error_spec_from_error,
    register_fastapi_exception_handlers,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register canonical exception handlers for the file API runtime."""
    register_fastapi_exception_handlers(
        app,
        domain_error_type=FileTransferError,
        adapt_domain_error=canonical_error_spec_from_error,
        validation_error_details=_validation_error_details,
        adapt_unhandled_error=_unhandled_error_spec,
        logger_name="errors",
    )


def _validation_error_details(
    exc: RequestValidationError,
) -> dict[str, object]:
    """Sanitize FastAPI validation details for public responses."""
    return {"errors": sanitize_validation_errors(errors=exc.errors())}


def _unhandled_error_spec(_: Exception) -> CanonicalErrorSpec:
    """Return the canonical internal-error transport payload."""
    err = internal_error("unexpected internal error")
    return canonical_error_spec_from_error(err)
