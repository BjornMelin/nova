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
    """
    Verify an access token and return the authenticated principal and its claims.
    
    Parameters:
        payload (TokenVerifyRequest): Verification request containing the token and any verification options.
    
    Returns:
        TokenVerifyResponse: The authenticated principal and associated token claims.
    """
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
    """
    Introspects an access token and returns whether it is active along with its claims and metadata.
    
    Parameters:
    	payload (IntrospectRequestDep): Request data for introspection (typically contains the token and optional token_type_hint).
    
    Returns:
    	TokenIntrospectResponse: Response indicating if the token is active; when active, includes token claims and related metadata.
    """
    return await service.introspect(payload)
