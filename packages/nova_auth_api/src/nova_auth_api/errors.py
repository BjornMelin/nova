"""Error definitions for nova-auth-api."""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any

from oidc_jwt_verifier import AuthError


@dataclass(slots=True)
class AuthApiError(Exception):
    """Domain error used by auth API handlers."""

    code: str
    message: str
    status_code: int = HTTPStatus.BAD_REQUEST
    details: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize ``Exception.args`` from message."""
        Exception.__init__(self, self.message)


def invalid_request(message: str) -> AuthApiError:
    """Return a canonical invalid request error."""
    return AuthApiError(
        code="validation_error",
        message=message,
        status_code=HTTPStatus.BAD_REQUEST,
    )


def unauthorized(
    message: str,
    *,
    www_authenticate: str | None = None,
) -> AuthApiError:
    """Return a canonical unauthorized error."""
    headers: dict[str, str] = {}
    if www_authenticate is not None:
        headers["WWW-Authenticate"] = www_authenticate
    return AuthApiError(
        code="unauthorized",
        message=message,
        status_code=HTTPStatus.UNAUTHORIZED,
        headers=headers,
    )


def forbidden(message: str) -> AuthApiError:
    """Return a canonical forbidden error."""
    return AuthApiError(
        code="forbidden",
        message=message,
        status_code=HTTPStatus.FORBIDDEN,
    )


def internal_error(message: str) -> AuthApiError:
    """Return a canonical internal service error."""
    return AuthApiError(
        code="internal_error",
        message=message,
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
    )


def from_oidc_auth_error(exc: AuthError) -> AuthApiError:
    """Convert ``oidc_jwt_verifier.AuthError`` into ``AuthApiError``."""
    code_value = getattr(exc, "code", "invalid_token")
    message_value = getattr(exc, "message", "token validation failed")
    status_value = getattr(exc, "status_code", 401)
    header = _www_authenticate_header(exc=exc)
    return AuthApiError(
        code=code_value if isinstance(code_value, str) else "invalid_token",
        message=(
            message_value
            if isinstance(message_value, str)
            else "token validation failed"
        ),
        status_code=status_value if isinstance(status_value, int) else 401,
        headers={"WWW-Authenticate": header} if header else {},
    )


def _www_authenticate_header(*, exc: AuthError) -> str | None:
    method = getattr(exc, "www_authenticate_header", None)
    if not callable(method):
        return None
    try:
        value = method()
    except Exception:
        return None
    if isinstance(value, str) and value:
        return value
    return None
