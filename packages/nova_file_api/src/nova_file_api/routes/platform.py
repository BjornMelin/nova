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
    IdempotencyMode,
    MetricsSummaryResponse,
    ReadinessResponse,
    ReleaseInfoResponse,
    ResourcePlanItem,
    ResourcePlanRequest,
    ResourcePlanResponse,
)
from nova_file_api.routes.common import emit_request_metric

ops_router = APIRouter(tags=["ops"])
platform_router = APIRouter(prefix="/v1", tags=["platform"])


@platform_router.get(
    "/capabilities",
    response_model=CapabilitiesResponse,
)
async def get_capabilities(
    context: RequestContextDep,
) -> CapabilitiesResponse:
    """Expose runtime capability declarations."""
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
    response_model=ResourcePlanResponse,
)
async def plan_resources(
    payload: ResourcePlanRequest,
    context: RequestContextDep,
) -> ResourcePlanResponse:
    """Plan supportability for requested resource keys."""
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
    response_model=ReleaseInfoResponse,
)
async def get_release_info(
    context: RequestContextDep,
) -> ReleaseInfoResponse:
    """Return service release metadata."""
    settings = context.container.settings
    return ReleaseInfoResponse(
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@ops_router.get(
    "/v1/health/live",
    response_model=HealthResponse,
)
async def health_live() -> HealthResponse:
    """Return liveness status."""
    return HealthResponse(ok=True)


@ops_router.get(
    "/v1/health/ready",
    response_model=ReadinessResponse,
)
async def health_ready(
    context: RequestContextDep,
    response: Response,
) -> ReadinessResponse:
    """Return readiness checks for traffic-critical dependencies."""
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
            job_queue = await context.run_blocking(
                container.job_service.publisher.healthcheck,
            )
        except Exception:
            logger.exception(
                "v1_health_ready_job_queue_healthcheck_failed",
                route="/v1/health/ready",
            )
            job_queue = False
    else:
        job_queue = True

    try:
        activity_store = await context.run_blocking(
            container.activity_store.healthcheck,
        )
    except Exception:
        logger.exception(
            "v1_health_ready_activity_store_healthcheck_failed",
            route="/v1/health/ready",
        )
        activity_store = False

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
    shared_cache_required = (
        container.settings.idempotency_enabled
        and container.settings.idempotency_mode
        == IdempotencyMode.SHARED_REQUIRED
    )
    is_ready = (
        checks["bucket_configured"]
        and (not shared_cache_required or checks["shared_cache"])
        and checks["job_queue"]
        and checks["auth_dependency"]
    )
    if not checks["bucket_configured"]:
        response.status_code = 503
    return ReadinessResponse(ok=is_ready, checks=checks)


@ops_router.get(
    "/metrics/summary",
    response_model=MetricsSummaryResponse,
)
async def metrics_summary(
    context: RequestContextDep,
) -> MetricsSummaryResponse:
    """Return low-cardinality metrics summary for dashboards."""
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
        activity=await context.run_blocking(container.activity_store.summary),
    )
