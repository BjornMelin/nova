"""Domain errors and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any


@dataclass(slots=True)
class FileTransferError(Exception):
    """Base domain exception returned as API error envelope."""

    code: str
    message: str
    status_code: int
    details: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


def invalid_request(
    message: str,
    *,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> FileTransferError:
    """Return a validation-style request error."""
    return FileTransferError(
        code="invalid_request",
        message=message,
        status_code=int(HTTPStatus.UNPROCESSABLE_ENTITY),
        details=details or {},
        headers=headers or {},
    )


def unauthorized(
    message: str,
    *,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> FileTransferError:
    """Return an unauthorized error."""
    return FileTransferError(
        code="unauthorized",
        message=message,
        status_code=int(HTTPStatus.UNAUTHORIZED),
        details=details or {},
        headers=headers or {},
    )


def forbidden(
    message: str,
    *,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> FileTransferError:
    """Return a forbidden error."""
    return FileTransferError(
        code="forbidden",
        message=message,
        status_code=int(HTTPStatus.FORBIDDEN),
        details=details or {},
        headers=headers or {},
    )


def not_found(
    message: str,
    *,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> FileTransferError:
    """Return a not found error."""
    return FileTransferError(
        code="not_found",
        message=message,
        status_code=int(HTTPStatus.NOT_FOUND),
        details=details or {},
        headers=headers or {},
    )


def conflict(
    message: str,
    *,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> FileTransferError:
    """Return a conflict error."""
    return FileTransferError(
        code="conflict",
        message=message,
        status_code=int(HTTPStatus.CONFLICT),
        details=details or {},
        headers=headers or {},
    )


def idempotency_conflict(
    message: str,
    *,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> FileTransferError:
    """Return an idempotency conflict error."""
    return FileTransferError(
        code="idempotency_conflict",
        message=message,
        status_code=int(HTTPStatus.CONFLICT),
        details=details or {},
        headers=headers or {},
    )


def upstream_s3_error(
    message: str,
    *,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> FileTransferError:
    """Return an upstream S3 failure error."""
    return FileTransferError(
        code="upstream_s3_error",
        message=message,
        status_code=int(HTTPStatus.BAD_GATEWAY),
        details=details or {},
        headers=headers or {},
    )


def queue_unavailable(
    message: str,
    *,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> FileTransferError:
    """Return queue-unavailable error for failed enqueue publishing."""
    return FileTransferError(
        code="queue_unavailable",
        message=message,
        status_code=int(HTTPStatus.SERVICE_UNAVAILABLE),
        details=details or {},
        headers=headers or {},
    )


def internal_error(
    message: str,
    *,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> FileTransferError:
    """Return a generic internal error."""
    return FileTransferError(
        code="internal_error",
        message=message,
        status_code=int(HTTPStatus.INTERNAL_SERVER_ERROR),
        details=details or {},
        headers=headers or {},
    )
