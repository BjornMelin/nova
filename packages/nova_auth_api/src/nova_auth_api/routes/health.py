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
    """Return liveness status."""
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
    """Return readiness status for token verification."""
    if not service.is_ready():
        raise service_unavailable("auth verifier unavailable")
    return HealthResponse(
        status="ok",
        service="nova-auth-api",
        request_id=request_id,
    )
