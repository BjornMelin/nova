"""Platform and operational routes for the canonical file API."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Response
from starlette.requests import Request

from nova_file_api.dependencies import (
    ActivityStoreDep,
    AuthenticatorDep,
    JobServiceDep,
    MetricsDep,
    SettingsDep,
    SharedCacheDep,
    authenticate_principal,
)
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
async def get_capabilities(settings: SettingsDep) -> CapabilitiesResponse:
    """Expose runtime capability declarations."""
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
    settings: SettingsDep,
) -> ResourcePlanResponse:
    """Plan supportability for requested resource keys."""
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
async def get_release_info(settings: SettingsDep) -> ReleaseInfoResponse:
    """Return service release metadata."""
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
    """Return liveness status."""
    return HealthResponse(ok=True)


@ops_router.get(
    "/v1/health/ready",
    operation_id=HEALTH_READY_OPERATION_ID,
    response_model=ReadinessResponse,
)
async def health_ready(
    response: Response,
    settings: SettingsDep,
    shared_cache: SharedCacheDep,
    job_service: JobServiceDep,
    activity_store: ActivityStoreDep,
    authenticator: AuthenticatorDep,
) -> ReadinessResponse:
    """Return readiness checks for the current runtime dependencies."""
    logger = structlog.get_logger("api")

    try:
        shared_cache_ready = await shared_cache.ping()
    except Exception:
        logger.exception(
            "v1_health_ready_shared_cache_ping_failed",
            route="/v1/health/ready",
        )
        shared_cache_ready = False

    if settings.jobs_enabled:
        job_queue = True
        try:
            publisher_ok = await job_service.publisher.healthcheck()
        except Exception:
            logger.exception(
                "v1_health_ready_job_queue_healthcheck_failed",
                route="/v1/health/ready",
            )
            publisher_ok = False
        try:
            repository_ok = await job_service.repository.healthcheck()
        except Exception:
            logger.exception(
                "v1_health_ready_job_repository_healthcheck_failed",
                route="/v1/health/ready",
            )
            repository_ok = False
        job_queue = publisher_ok and repository_ok
    else:
        job_queue = True

    try:
        activity_store_ready = await activity_store.healthcheck()
    except Exception:
        logger.exception(
            "v1_health_ready_activity_store_healthcheck_failed",
            route="/v1/health/ready",
        )
        activity_store_ready = False

    if settings.auth_mode == AuthMode.SAME_ORIGIN:
        auth_dependency = True
    else:
        try:
            auth_dependency = await authenticator.healthcheck()
        except Exception:
            logger.exception(
                "v1_health_ready_auth_dependency_healthcheck_failed",
                route="/v1/health/ready",
            )
            auth_dependency = False

    checks = {
        "bucket_configured": bool(settings.file_transfer_bucket.strip()),
        "shared_cache": shared_cache_ready,
        "job_queue": job_queue,
        "activity_store": activity_store_ready,
        "auth_dependency": auth_dependency,
    }
    is_ready = all(checks.values())
    if not is_ready:
        response.status_code = 503
    return ReadinessResponse(ok=is_ready, checks=checks)


@ops_router.get(
    "/metrics/summary",
    operation_id=METRICS_SUMMARY_OPERATION_ID,
    response_model=MetricsSummaryResponse,
)
async def metrics_summary(
    request: Request,
    settings: SettingsDep,
    metrics: MetricsDep,
    activity_store: ActivityStoreDep,
    authenticator: AuthenticatorDep,
) -> MetricsSummaryResponse:
    """Return low-cardinality metrics summary for dashboards."""
    principal = await authenticate_principal(
        request=request,
        authenticator=authenticator,
        session_id=None,
    )
    if (
        settings.auth_mode != AuthMode.SAME_ORIGIN
        and "metrics:read" not in principal.permissions
    ):
        raise forbidden("missing metrics:read permission")

    activity_summary = await activity_store.summary()
    emit_request_metric(
        metrics=metrics,
        route="metrics_summary",
        status="ok",
    )
    return MetricsSummaryResponse(
        counters=metrics.counters_snapshot(),
        latencies_ms=metrics.latency_snapshot(),
        activity=activity_summary,
    )
