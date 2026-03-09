"""FastAPI dependency helpers for nova-auth-api."""

from __future__ import annotations

from typing import Annotated, cast

from anyio.abc import CapacityLimiter
from fastapi import Depends, Request

from nova_auth_api.service import TokenVerificationService

_AUTH_SERVICE_NOT_INITIALIZED = "auth service not initialized"
_BLOCKING_IO_LIMITER_NOT_INITIALIZED = (
    "application blocking I/O limiter is not initialized"
)
BLOCKING_IO_LIMITER_STATE_KEY = "blocking_io_thread_limiter"


def get_token_verification_service(
    request: Request,
) -> TokenVerificationService:
    """Return the initialized token verification service."""
    value = getattr(request.app.state, "auth_service", None)
    if isinstance(value, TokenVerificationService):
        return value
    raise RuntimeError(_AUTH_SERVICE_NOT_INITIALIZED)


def get_blocking_io_limiter(request: Request) -> CapacityLimiter:
    """Return the app-scoped limiter reserved for blocking auth work."""
    limiter = getattr(request.app.state, BLOCKING_IO_LIMITER_STATE_KEY, None)
    if limiter is None:
        raise RuntimeError(_BLOCKING_IO_LIMITER_NOT_INITIALIZED)
    return cast(CapacityLimiter, limiter)


TokenVerificationServiceDep = Annotated[
    TokenVerificationService, Depends(get_token_verification_service)
]
