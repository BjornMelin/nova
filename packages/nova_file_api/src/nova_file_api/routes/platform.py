"""Platform and operational routes for the canonical file API."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Response

from nova_file_api.dependencies import RequestContextDep
from nova_file_api.errors import forbidden
from nova_file_api.models import (
    AuthMode,
    CapabilitiesResponse,
    CapabilityDescriptor,
    HealthResponse,
    MetricsSummaryResponse,
    ReadinessResponse,
    ReleaseInfoResponse,
    ResourcePlanItem,
    ResourcePlanRequest,
    ResourcePlanResponse,
)
from nova_file_api.operation_ids import (
    GET_CAPABILITIES_OPERATION_ID,
    GET_RELEASE_INFO_OPERATION_ID,
    HEALTH_LIVE_OPERATION_ID,
    HEALTH_READY_OPERATION_ID,
    METRICS_SUMMARY_OPERATION_ID,
    PLAN_RESOURCES_OPERATION_ID,
)
from nova_file_api.routes.common import emit_request_metric

ops_router = APIRouter(tags=["ops"])
platform_router = APIRouter(prefix="/v1", tags=["platform"])


@platform_router.get(
    "/capabilities",
    operation_id=GET_CAPABILITIES_OPERATION_ID,
    response_model=CapabilitiesResponse,
)
async def get_capabilities(
    context: RequestContextDep,
) -> CapabilitiesResponse:
    """
    Declare runtime capabilities exposed by the service.
    
    Returns:
        CapabilitiesResponse: A response containing a list of CapabilityDescriptor entries that indicate which runtime features (e.g., jobs, jobs.events.poll, transfers) are enabled.
    """
    settings = context.container.settings
    capabilities = [
        CapabilityDescriptor(key="jobs", enabled=settings.jobs_enabled),
        CapabilityDescriptor(
            key="jobs.events.poll",
            enabled=settings.jobs_enabled,
        ),
        CapabilityDescriptor(
            key="transfers",
            enabled=settings.file_transfer_enabled,
        ),
    ]
    return CapabilitiesResponse(capabilities=capabilities)


@platform_router.post(
    "/resources/plan",
    operation_id=PLAN_RESOURCES_OPERATION_ID,
    response_model=ResourcePlanResponse,
)
async def plan_resources(
    payload: ResourcePlanRequest,
    context: RequestContextDep,
) -> ResourcePlanResponse:
    """
    Produce a resource compatibility plan for the requested resource keys.
    
    For each resource in payload.resources, returns a ResourcePlanItem indicating whether the resource is supported and, if not, a reason. Support is determined from a fixed available set {"jobs", "transfers", "downloads", "uploads"} and is further constrained by runtime settings: if settings.jobs_enabled is False any "jobs" item is marked unsupported with reason "jobs_disabled"; if settings.file_transfer_enabled is False any "transfers", "downloads", or "uploads" item is marked unsupported with reason "file_transfers_disabled".
    
    Parameters:
        payload (ResourcePlanRequest): Request containing the list of resource keys to evaluate.
        context (RequestContextDep): Request context carrying runtime settings.
    
    Returns:
        ResourcePlanResponse: Response containing a plan (list of ResourcePlanItem) where each item has `supported` set to `true` when the resource is available and not disabled by settings, otherwise `false` with a concrete `reason` such as "unsupported_resource", "jobs_disabled", or "file_transfers_disabled".
    """
    settings = context.container.settings
    available = {"jobs", "transfers", "downloads", "uploads"}
    plan = [
        ResourcePlanItem(
            resource=resource,
            supported=resource in available,
            reason=None if resource in available else "unsupported_resource",
        )
        for resource in payload.resources
    ]
    if not settings.jobs_enabled:
        plan = [
            item.model_copy(
                update={"supported": False, "reason": "jobs_disabled"}
            )
            if item.resource == "jobs"
            else item
            for item in plan
        ]
    if not settings.file_transfer_enabled:
        plan = [
            item.model_copy(
                update={
                    "supported": False,
                    "reason": "file_transfers_disabled",
                }
            )
            if item.resource in {"transfers", "downloads", "uploads"}
            else item
            for item in plan
        ]
    return ResourcePlanResponse(plan=plan)


@platform_router.get(
    "/releases/info",
    operation_id=GET_RELEASE_INFO_OPERATION_ID,
    response_model=ReleaseInfoResponse,
)
async def get_release_info(
    context: RequestContextDep,
) -> ReleaseInfoResponse:
    """
    Provide the service's release metadata.
    
    Returns:
        ReleaseInfoResponse: Contains `name` (application name), `version` (application version), and `environment` (deployment environment).
    """
    settings = context.container.settings
    return ReleaseInfoResponse(
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@ops_router.get(
    "/v1/health/live",
    operation_id=HEALTH_LIVE_OPERATION_ID,
    response_model=HealthResponse,
)
async def health_live() -> HealthResponse:
    """
    Indicates whether the service is alive.
    
    Returns:
        HealthResponse: Response with ok=True.
    """
    return HealthResponse(ok=True)


@ops_router.get(
    "/v1/health/ready",
    operation_id=HEALTH_READY_OPERATION_ID,
    response_model=ReadinessResponse,
)
async def health_ready(
    context: RequestContextDep,
    response: Response,
) -> ReadinessResponse:
    """
    Determine readiness of traffic-critical dependencies.
    
    Performs health checks for shared cache, job queue (if enabled), activity store,
    and authentication dependency (unless SAME_ORIGIN). Sets the HTTP response
    status to 503 when any check indicates failure.
    
    Parameters:
        response (Response): HTTP response object; its status_code will be set to 503 when not ready.
    
    Returns:
        ReadinessResponse: Contains `ok` indicating overall readiness and `checks` mapping
        individual dependency names to their boolean health status.
    """
    container = context.container
    logger = structlog.get_logger("api")

    try:
        shared_cache = await container.shared_cache.ping()
    except Exception:
        logger.exception(
            "v1_health_ready_shared_cache_ping_failed",
            route="/v1/health/ready",
        )
        shared_cache = False

    if container.settings.jobs_enabled:
        try:
            job_queue = await container.job_service.publisher.healthcheck()
        except Exception:
            logger.exception(
                "v1_health_ready_job_queue_healthcheck_failed",
                route="/v1/health/ready",
            )
            job_queue = False
    else:
        job_queue = True

    try:
        activity_store = await container.activity_store.healthcheck()
    except Exception:
        logger.exception(
            "v1_health_ready_activity_store_healthcheck_failed",
            route="/v1/health/ready",
        )
        activity_store = False

    if container.settings.auth_mode == AuthMode.SAME_ORIGIN:
        auth_dependency = True
    else:
        try:
            auth_dependency = await container.authenticator.healthcheck()
        except Exception:
            logger.exception(
                "v1_health_ready_auth_dependency_healthcheck_failed",
                route="/v1/health/ready",
            )
            auth_dependency = False

    checks = {
        "bucket_configured": bool(
            container.settings.file_transfer_bucket.strip()
        ),
        "shared_cache": shared_cache,
        "job_queue": job_queue,
        "activity_store": activity_store,
        "auth_dependency": auth_dependency,
    }
    is_ready = (
        checks["bucket_configured"]
        and checks["shared_cache"]
        and checks["job_queue"]
        and checks["activity_store"]
        and checks["auth_dependency"]
    )
    if not is_ready:
        response.status_code = 503
    return ReadinessResponse(ok=is_ready, checks=checks)


@ops_router.get(
    "/metrics/summary",
    operation_id=METRICS_SUMMARY_OPERATION_ID,
    response_model=MetricsSummaryResponse,
)
async def metrics_summary(
    context: RequestContextDep,
) -> MetricsSummaryResponse:
    """
    Provide a low-cardinality metrics summary used by dashboards.
    
    Returns:
        MetricsSummaryResponse: Contains:
            - counters: mapping of metric names to their current counts.
            - latencies_ms: latency measurements in milliseconds.
            - activity: summary object from the activity store.
    """
    container = context.container
    principal = await context.authenticate(session_id=None)
    if (
        container.settings.auth_mode != AuthMode.SAME_ORIGIN
        and "metrics:read" not in principal.permissions
    ):
        raise forbidden("missing metrics:read permission")

    emit_request_metric(
        container=container,
        route="metrics_summary",
        status="ok",
    )
    return MetricsSummaryResponse(
        counters=container.metrics.counters_snapshot(),
        latencies_ms=container.metrics.latency_snapshot(),
        activity=await container.activity_store.summary(),
    )
