"""Token routes for nova-auth-api."""

from __future__ import annotations

from fastapi import APIRouter

from nova_auth_api.dependencies import TokenVerificationServiceDep
from nova_auth_api.models import (
    TokenIntrospectResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
)
from nova_auth_api.operation_ids import (
    INTROSPECT_TOKEN_OPERATION_ID,
    VERIFY_TOKEN_OPERATION_ID,
)
from nova_auth_api.request_parsing import (
    INTROSPECT_REQUEST_BODY,
    IntrospectRequestDep,
)

router = APIRouter(prefix="/v1/token", tags=["token"])


@router.post(
    "/verify",
    response_model=TokenVerifyResponse,
    operation_id=VERIFY_TOKEN_OPERATION_ID,
)
async def verify_token(
    payload: TokenVerifyRequest,
    service: TokenVerificationServiceDep,
) -> TokenVerifyResponse:
    """Verify access token and return principal plus claims."""
    return await service.verify(payload)


@router.post(
    "/introspect",
    response_model=TokenIntrospectResponse,
    operation_id=INTROSPECT_TOKEN_OPERATION_ID,
    openapi_extra={"requestBody": INTROSPECT_REQUEST_BODY},
)
async def introspect_token(
    payload: IntrospectRequestDep,
    service: TokenVerificationServiceDep,
) -> TokenIntrospectResponse:
    """Introspect token and return active status plus claim details."""
    return await service.introspect(payload)
