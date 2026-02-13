"""Error types for file transfer workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any


@dataclass(slots=True)
class FileTransferError(Exception):
    """Base exception for package-level file transfer errors."""

    code: str
    message: str
    status_code: int = HTTPStatus.BAD_REQUEST
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize ``Exception.args`` for exception interoperability."""
        Exception.__init__(self, self.message)

    def __str__(self) -> str:
        """Return a user-facing summary string."""
        return self.message


def validation_error(
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> FileTransferError:
    """Build a validation error instance."""
    return FileTransferError(
        code="validation_error",
        message=message,
        status_code=HTTPStatus.BAD_REQUEST,
        details=details or {},
    )


def forbidden_error(
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> FileTransferError:
    """Build a forbidden error instance."""
    return FileTransferError(
        code="forbidden",
        message=message,
        status_code=HTTPStatus.FORBIDDEN,
        details=details or {},
    )


def conflict_error(
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> FileTransferError:
    """Build a conflict error instance."""
    return FileTransferError(
        code="conflict",
        message=message,
        status_code=HTTPStatus.CONFLICT,
        details=details or {},
    )


def internal_error(
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> FileTransferError:
    """Build an internal error instance."""
    return FileTransferError(
        code="internal_error",
        message=message,
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        details=details or {},
    )
