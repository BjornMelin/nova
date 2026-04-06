"""Platform and operational routes for the canonical file API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, cast

import structlog
from fastapi import APIRouter, Query, Response

from nova_file_api.config import Settings
from nova_file_api.dependencies import (
    ActivityStoreDep,
    AuthenticatorDep,
    ExportServiceDep,
    IdempotencyStoreDep,
    MetricsDep,
    PrincipalDep,
    SettingsDep,
    TransferServiceDep,
)
from nova_file_api.errors import forbidden
from nova_file_api.models import (
    CapabilitiesResponse,
    CapabilityDescriptor,
    HealthResponse,
    MetricsSummaryResponse,
    ReadinessResponse,
    ReleaseInfoResponse,
    ResourcePlanItem,
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
    emit_request_metric,
)
from nova_file_api.transfer_config import transfer_config_from_settings
from nova_file_api.transfer_policy import (
    TransferPolicy,
    resolve_transfer_policy,
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
    settings: SettingsDep,
    transfer_service: TransferServiceDep,
) -> CapabilitiesResponse:
    """Expose runtime capability declarations."""
    policy = await _resolve_capabilities_policy(
        settings=settings,
        transfer_service=transfer_service,
    )
    capabilities = [
        CapabilityDescriptor(key="exports", enabled=settings.exports_enabled),
        CapabilityDescriptor(
            key="exports.status.poll",
            enabled=settings.exports_enabled,
        ),
        CapabilityDescriptor(
            key="transfers",
            enabled=settings.file_transfer_enabled,
        ),
        CapabilityDescriptor(
            key="transfers.policy",
            enabled=settings.file_transfer_enabled,
            details={
                "policy_id": policy.policy_id,
                "policy_version": policy.policy_version,
                "max_concurrency_hint": policy.max_concurrency_hint,
                "sign_batch_size_hint": policy.sign_batch_size_hint,
                "target_upload_part_count": policy.target_upload_part_count,
                "minimum_part_size_bytes": policy.minimum_part_size_bytes,
                "maximum_part_size_bytes": policy.maximum_part_size_bytes,
                "accelerate_enabled": policy.accelerate_enabled,
                "checksum_algorithm": policy.checksum_algorithm,
                "checksum_mode": policy.checksum_mode,
                "resumable_ttl_seconds": policy.resumable_ttl_seconds,
                "active_multipart_upload_limit": (
                    policy.active_multipart_upload_limit
                ),
                "daily_ingress_budget_bytes": (
                    policy.daily_ingress_budget_bytes
                ),
                "sign_requests_per_upload_limit": (
                    policy.sign_requests_per_upload_limit
                ),
                "large_export_worker_threshold_bytes": (
                    policy.large_export_worker_threshold_bytes
                ),
            },
        ),
    ]
    return CapabilitiesResponse(capabilities=capabilities)


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
    settings: SettingsDep,
    transfer_service: TransferServiceDep,
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
    policy = await _resolve_capabilities_policy(
        settings=settings,
        transfer_service=transfer_service,
        workload_class=workload_class,
        policy_hint=policy_hint,
    )
    return TransferCapabilitiesResponse(
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        max_upload_bytes=policy.max_upload_bytes,
        multipart_threshold_bytes=policy.multipart_threshold_bytes,
        target_upload_part_count=policy.target_upload_part_count,
        minimum_part_size_bytes=policy.minimum_part_size_bytes,
        maximum_part_size_bytes=policy.maximum_part_size_bytes,
        max_concurrency_hint=policy.max_concurrency_hint,
        sign_batch_size_hint=policy.sign_batch_size_hint,
        accelerate_enabled=policy.accelerate_enabled,
        checksum_algorithm=policy.checksum_algorithm,
        checksum_mode=policy.checksum_mode,
        resumable_ttl_seconds=policy.resumable_ttl_seconds,
        active_multipart_upload_limit=policy.active_multipart_upload_limit,
        daily_ingress_budget_bytes=policy.daily_ingress_budget_bytes,
        sign_requests_per_upload_limit=policy.sign_requests_per_upload_limit,
        large_export_worker_threshold_bytes=(
            policy.large_export_worker_threshold_bytes
        ),
    )


async def _resolve_capabilities_policy(
    *,
    settings: Settings,
    transfer_service: object,
    workload_class: str | None = None,
    policy_hint: str | None = None,
) -> TransferPolicy:
    """Resolve the effective transfer policy for the capabilities endpoint."""
    resolver = getattr(transfer_service, "resolve_policy", None)
    if callable(resolver):
        resolve_fn = cast(
            Callable[..., Awaitable[TransferPolicy]],
            resolver,
        )
        try:
            result = await resolve_fn(
                scope_id=None,
                workload_class=workload_class,
                policy_hint=policy_hint,
            )
        except TypeError:
            try:
                result = await resolve_fn(
                    scope_id=None,
                    policy_hint=policy_hint,
                )
            except TypeError:
                result = await resolve_fn(scope_id=None)
        return result
    return resolve_transfer_policy(
        config=transfer_config_from_settings(settings)
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
    settings: SettingsDep,
) -> ResourcePlanResponse:
    """Plan supportability for requested resource keys."""
    available = {"exports", "transfers", "downloads", "uploads"}
    plan = [
        ResourcePlanItem(
            resource=resource,
            supported=resource in available,
            reason=None if resource in available else "unsupported_resource",
        )
        for resource in payload.resources
    ]
    if not settings.exports_enabled:
        plan = [
            item.model_copy(
                update={"supported": False, "reason": "exports_disabled"}
            )
            if item.resource == "exports"
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
    summary="Get public release metadata",
    description=(
        "Return public release metadata used by browser clients, diagnostics, "
        "and deploy canaries."
    ),
    response_description="Release name, version, and environment metadata.",
)
async def get_release_info(settings: SettingsDep) -> ReleaseInfoResponse:
    """Return public release metadata for browser and deploy canaries."""
    return ReleaseInfoResponse(
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


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
        "Readiness status plus per-dependency readiness checks."
    ),
    responses=READINESS_UNAVAILABLE_RESPONSE,
)
async def health_ready(
    response: Response,
    settings: SettingsDep,
    idempotency_store: IdempotencyStoreDep,
    export_service: ExportServiceDep,
    transfer_service: TransferServiceDep,
    activity_store: ActivityStoreDep,
    authenticator: AuthenticatorDep,
) -> ReadinessResponse:
    """Return readiness checks for traffic-critical dependencies."""
    logger = structlog.get_logger("api")

    try:
        idempotency_store_ready = await idempotency_store.healthcheck()
    except Exception:
        logger.exception(
            "v1_health_ready_idempotency_store_healthcheck_failed",
            route="/v1/health/ready",
        )
        idempotency_store_ready = False

    if settings.exports_enabled:
        export_runtime = True
        try:
            publisher_ok = await export_service.publisher.healthcheck()
        except Exception:
            logger.exception(
                "v1_health_ready_export_queue_healthcheck_failed",
                route="/v1/health/ready",
            )
            publisher_ok = False
        try:
            repository_ok = await export_service.repository.healthcheck()
        except Exception:
            logger.exception(
                "v1_health_ready_export_repository_healthcheck_failed",
                route="/v1/health/ready",
            )
            repository_ok = False
        export_runtime = publisher_ok and repository_ok
    else:
        export_runtime = True

    try:
        activity_store_ready = await activity_store.healthcheck()
    except Exception:
        logger.exception(
            "v1_health_ready_activity_store_healthcheck_failed",
            route="/v1/health/ready",
        )
        activity_store_ready = False

    try:
        transfer_runtime_ready = await transfer_service.healthcheck()
    except Exception:
        logger.exception(
            "v1_health_ready_transfer_runtime_healthcheck_failed",
            route="/v1/health/ready",
        )
        transfer_runtime_ready = False

    try:
        auth_dependency = await authenticator.healthcheck()
    except Exception:
        logger.exception(
            "v1_health_ready_auth_dependency_healthcheck_failed",
            route="/v1/health/ready",
        )
        auth_dependency = False

    checks = {
        "bucket_configured": bool(
            (settings.file_transfer_bucket or "").strip()
        ),
        "idempotency_store": idempotency_store_ready,
        "export_runtime": export_runtime,
        "activity_store": activity_store_ready,
        "transfer_runtime": transfer_runtime_ready,
        "auth_dependency": auth_dependency,
    }
    required_checks: tuple[str, ...] = (
        "bucket_configured",
        "auth_dependency",
        "export_runtime",
        "transfer_runtime",
    )
    if settings.idempotency_enabled:
        required_checks = (*required_checks, "idempotency_store")
    is_ready = all(checks[name] for name in required_checks)
    if not is_ready:
        response.status_code = 503
    return ReadinessResponse(ok=is_ready, checks=checks)


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
    metrics: MetricsDep,
    activity_store: ActivityStoreDep,
    principal: PrincipalDep,
) -> MetricsSummaryResponse:
    """Return low-cardinality metrics summary for dashboards."""
    if "metrics:read" not in principal.permissions:
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
