"""Health routes for nova-auth-api."""

from __future__ import annotations

from fastapi import APIRouter

from nova_auth_api.dependencies import TokenVerificationServiceDep
from nova_auth_api.errors import service_unavailable
from nova_auth_api.middleware import RequestIdDep
from nova_auth_api.models import HealthResponse
from nova_auth_api.operation_ids import (
    HEALTH_LIVE_OPERATION_ID,
    HEALTH_READY_OPERATION_ID,
)

router = APIRouter(prefix="/v1/health", tags=["health"])


@router.get(
    "/live",
    response_model=HealthResponse,
    operation_id=HEALTH_LIVE_OPERATION_ID,
)
async def health_live(request_id: RequestIdDep) -> HealthResponse:
    """
    Return the service liveness information.
    
    Returns:
        HealthResponse: HealthResponse with status "ok", service "nova-auth-api", and the provided request_id.
    """
    return HealthResponse(
        status="ok",
        service="nova-auth-api",
        request_id=request_id,
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    operation_id=HEALTH_READY_OPERATION_ID,
)
async def health_ready(
    request_id: RequestIdDep,
    service: TokenVerificationServiceDep,
) -> HealthResponse:
    """
    Return a readiness HealthResponse when the token verification service reports ready.
    
    Parameters:
        request_id (str): Request identifier provided by the RequestIdDep dependency.
    
    Returns:
        HealthResponse: Object with status "ok", service "nova-auth-api", and the provided request_id.
    
    Raises:
        service_unavailable: If the token verification service is not ready (message "auth verifier unavailable").
    """
    if not service.is_ready():
        raise service_unavailable("auth verifier unavailable")
    return HealthResponse(
        status="ok",
        service="nova-auth-api",
        request_id=request_id,
    )