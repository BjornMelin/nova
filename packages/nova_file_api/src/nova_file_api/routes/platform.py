"""Platform and operational routes for the canonical file API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from nova_file_api.dependencies import (
    PlatformApplicationServiceDep,
    PrincipalDep,
    ReadinessServiceDep,
)
from nova_file_api.models import (
    CapabilitiesResponse,
    HealthResponse,
    MetricsSummaryResponse,
    ReadinessResponse,
    ReleaseInfoResponse,
    ResourcePlanRequest,
    ResourcePlanResponse,
    TransferCapabilitiesResponse,
)
from nova_file_api.operation_ids import (
    GET_CAPABILITIES_OPERATION_ID,
    GET_RELEASE_INFO_OPERATION_ID,
    GET_TRANSFER_CAPABILITIES_OPERATION_ID,
    HEALTH_LIVE_OPERATION_ID,
    HEALTH_READY_OPERATION_ID,
    METRICS_SUMMARY_OPERATION_ID,
    PLAN_RESOURCES_OPERATION_ID,
)
from nova_file_api.routes.common import (
    READINESS_UNAVAILABLE_RESPONSE,
    UNAUTHORIZED_AND_FORBIDDEN_RESPONSES,
    VALIDATION_ERROR_RESPONSE,
)

ops_router = APIRouter(tags=["ops"])
platform_router = APIRouter(prefix="/v1", tags=["platform"])


@platform_router.get(
    "/capabilities",
    operation_id=GET_CAPABILITIES_OPERATION_ID,
    response_model=CapabilitiesResponse,
    summary="Get runtime capability declarations",
    description=(
        "Expose the major runtime capabilities enabled for the current Nova "
        "deployment."
    ),
    response_description="Runtime capability declarations for the deployment.",
)
async def get_capabilities(
    platform_application_service: PlatformApplicationServiceDep,
) -> CapabilitiesResponse:
    """Expose runtime capability declarations."""
    return await platform_application_service.get_capabilities()


@platform_router.get(
    "/capabilities/transfers",
    operation_id=GET_TRANSFER_CAPABILITIES_OPERATION_ID,
    response_model=TransferCapabilitiesResponse,
    summary="Get the effective transfer policy",
    description=(
        "Expose the current transfer policy envelope that browser and native "
        "upload clients should honor."
    ),
    response_description="Effective transfer policy metadata and limits.",
)
async def get_transfer_capabilities(
    platform_application_service: PlatformApplicationServiceDep,
    workload_class: Annotated[
        str | None,
        Query(
            max_length=128,
            description=(
                "Optional workload-class hint used to resolve a narrower "
                "effective transfer policy."
            ),
        ),
    ] = None,
    policy_hint: Annotated[
        str | None,
        Query(
            max_length=128,
            description=(
                "Optional policy hint evaluated by the transfer policy "
                "resolver."
            ),
        ),
    ] = None,
) -> TransferCapabilitiesResponse:
    """Expose the current transfer policy envelope."""
    return await platform_application_service.get_transfer_capabilities(
        workload_class=workload_class,
        policy_hint=policy_hint,
    )


@platform_router.post(
    "/resources/plan",
    operation_id=PLAN_RESOURCES_OPERATION_ID,
    response_model=ResourcePlanResponse,
    summary="Plan resource support",
    description=(
        "Report whether each requested resource is currently supported in the "
        "active deployment."
    ),
    response_description=(
        "Supportability decisions for each requested resource."
    ),
    responses=VALIDATION_ERROR_RESPONSE,
)
async def plan_resources(
    payload: ResourcePlanRequest,
    platform_application_service: PlatformApplicationServiceDep,
) -> ResourcePlanResponse:
    """Plan supportability for requested resource keys."""
    return platform_application_service.plan_resources(payload=payload)


@platform_router.get(
    "/releases/info",
    operation_id=GET_RELEASE_INFO_OPERATION_ID,
    response_model=ReleaseInfoResponse,
    summary="Get public release metadata",
    description=(
        "Return public release metadata used by browser clients, diagnostics, "
        "and deploy canaries."
    ),
    response_description="Release name, version, and environment metadata.",
)
async def get_release_info(
    platform_application_service: PlatformApplicationServiceDep,
) -> ReleaseInfoResponse:
    """Return public release metadata for browser and deploy canaries."""
    return platform_application_service.get_release_info()


@ops_router.get(
    "/v1/health/live",
    operation_id=HEALTH_LIVE_OPERATION_ID,
    response_model=HealthResponse,
    summary="Check liveness",
    description="Return a shallow liveness signal for the API runtime process.",
    response_description="Liveness status for the API runtime.",
)
async def health_live() -> HealthResponse:
    """Return liveness status."""
    return HealthResponse(ok=True)


@ops_router.get(
    "/v1/health/ready",
    operation_id=HEALTH_READY_OPERATION_ID,
    response_model=ReadinessResponse,
    summary="Check readiness",
    description=(
        "Return readiness checks for traffic-critical dependencies such as "
        "auth, transfers, exports, and idempotency."
    ),
    response_description=(
        "Readiness status plus per-dependency results for the live traffic "
        "gates only."
    ),
    responses=READINESS_UNAVAILABLE_RESPONSE,
)
async def health_ready(
    response: Response,
    readiness_service: ReadinessServiceDep,
) -> ReadinessResponse:
    """Return readiness checks for traffic-critical dependencies."""
    readiness = await readiness_service.get_readiness()
    if not readiness.ok:
        response.status_code = 503
    return readiness


@ops_router.get(
    "/metrics/summary",
    operation_id=METRICS_SUMMARY_OPERATION_ID,
    response_model=MetricsSummaryResponse,
    summary="Get metrics summary",
    description=(
        "Return low-cardinality counters, latency summaries, and activity "
        "rollups for dashboards."
    ),
    response_description="Low-cardinality metrics and activity summary.",
    responses=UNAUTHORIZED_AND_FORBIDDEN_RESPONSES,
)
async def metrics_summary(
    platform_application_service: PlatformApplicationServiceDep,
    principal: PrincipalDep,
) -> MetricsSummaryResponse:
    """Return low-cardinality metrics summary for dashboards."""
    return await platform_application_service.get_metrics_summary(
        principal=principal,
    )
