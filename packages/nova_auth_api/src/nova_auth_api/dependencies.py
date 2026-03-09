"""FastAPI dependency helpers for nova-auth-api."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from nova_auth_api.service import TokenVerificationService

BLOCKING_IO_LIMITER_STATE_KEY = "blocking_io_limiter"
_AUTH_SERVICE_NOT_INITIALIZED = "auth service is not initialized"


def get_token_verification_service(
    request: Request,
) -> TokenVerificationService:
    """Return the initialized token verification service.

    Args:
        request: FastAPI request carrying application state.

    Returns:
        The initialized token verification service.

    Raises:
        RuntimeError: If the auth service has not been initialized.
    """
    value = getattr(request.app.state, "auth_service", None)
    if isinstance(value, TokenVerificationService):
        return value
    raise RuntimeError(_AUTH_SERVICE_NOT_INITIALIZED)


TokenVerificationServiceDep = Annotated[
    TokenVerificationService,
    Depends(get_token_verification_service),
]
