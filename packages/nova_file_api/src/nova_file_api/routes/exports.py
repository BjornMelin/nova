"""Export-domain routes for the canonical file API."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request, status

from nova_file_api.activity import ActivityStore
from nova_file_api.dependencies import (
    ActivityStoreDep,
    ExportServiceDep,
    IdempotencyStoreDep,
    MetricsDep,
    PrincipalDep,
    SettingsDep,
)
from nova_file_api.errors import forbidden
from nova_file_api.exports import ExportService
from nova_file_api.guarded_mutation import run_guarded_mutation
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    CreateExportRequest,
    ErrorEnvelope,
    ExportListResponse,
    ExportResource,
    Principal,
)
from nova_file_api.operation_ids import (
    CANCEL_EXPORT_OPERATION_ID,
    CREATE_EXPORT_OPERATION_ID,
    GET_EXPORT_OPERATION_ID,
    LIST_EXPORTS_OPERATION_ID,
)
from nova_file_api.routes.common import (
    COMMON_ERROR_RESPONSES,
    EXPORT_MUTATION_UNAVAILABLE_RESPONSE,
    IDEMPOTENCY_CONFLICT_RESPONSE,
    ExportsLimitQuery,
    IdempotencyKeyHeader,
    emit_request_metric,
    validated_idempotency_key,
)
from nova_runtime_support import request_id_from_request

exports_router = APIRouter(
    prefix="/v1",
    tags=["exports"],
    responses=COMMON_ERROR_RESPONSES,
)


@exports_router.post(
    "/exports",
    operation_id=CREATE_EXPORT_OPERATION_ID,
    response_model=ExportResource,
    status_code=status.HTTP_201_CREATED,
    responses=(
        IDEMPOTENCY_CONFLICT_RESPONSE | EXPORT_MUTATION_UNAVAILABLE_RESPONSE
    ),
)
async def create_export(
    payload: CreateExportRequest,
    request: Request,
    settings: SettingsDep,
    metrics: MetricsDep,
    export_service: ExportServiceDep,
    activity_store: ActivityStoreDep,
    idempotency_store: IdempotencyStoreDep,
    principal: PrincipalDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ExportResource:
    """Create an explicit export workflow resource."""
    if not settings.jobs_enabled:
        raise forbidden("exports API is disabled")

    key = validated_idempotency_key(
        settings=settings,
        idempotency_key=idempotency_key,
    )
    return await _create_export_core(
        request=request,
        metrics=metrics,
        export_service=export_service,
        activity_store=activity_store,
        idempotency_store=idempotency_store,
        payload=payload,
        principal=principal,
        idempotency_key=key,
    )


@exports_router.get(
    "/exports/{export_id}",
    operation_id=GET_EXPORT_OPERATION_ID,
    response_model=ExportResource,
    responses={
        404: {
            "model": ErrorEnvelope,
            "description": "Not Found - Export resource was not found.",
        }
    },
)
async def get_export(
    export_id: str,
    metrics: MetricsDep,
    export_service: ExportServiceDep,
    activity_store: ActivityStoreDep,
    principal: PrincipalDep,
) -> ExportResource:
    """Return the caller-owned export resource."""
    try:
        export = await export_service.get(
            export_id=export_id,
            scope_id=principal.scope_id,
        )
    except Exception as exc:
        await _record_export_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="exports_get_failure_total",
            route_metric="exports_get",
            log_event="exports_get_request_failed",
            route_path="/v1/exports/{export_id}",
            activity_event_type="exports_get_failure",
            exc=exc,
            extra={"export_id": export_id},
        )
        raise

    try:
        metrics.incr("exports_get_total")
        emit_request_metric(metrics=metrics, route="exports_get", status="ok")
    except Exception:
        structlog.get_logger("api").exception(
            "exports_get_success_side_effects_failed",
            route="/v1/exports/{export_id}",
            scope_id=principal.scope_id,
            export_id=export_id,
        )
    return ExportResource.from_record(export)


@exports_router.get(
    "/exports",
    operation_id=LIST_EXPORTS_OPERATION_ID,
    response_model=ExportListResponse,
)
async def list_exports(
    export_service: ExportServiceDep,
    principal: PrincipalDep,
    limit: ExportsLimitQuery = 50,
) -> ExportListResponse:
    """List caller-owned exports with most recent first."""
    exports = await export_service.list_for_scope(
        scope_id=principal.scope_id,
        limit=limit,
    )
    return ExportListResponse(
        exports=[ExportResource.from_record(export) for export in exports]
    )


@exports_router.post(
    "/exports/{export_id}/cancel",
    operation_id=CANCEL_EXPORT_OPERATION_ID,
    response_model=ExportResource,
    responses={
        404: {
            "model": ErrorEnvelope,
            "description": "Not Found - Export resource was not found.",
        }
    },
)
async def cancel_export(
    export_id: str,
    metrics: MetricsDep,
    export_service: ExportServiceDep,
    activity_store: ActivityStoreDep,
    principal: PrincipalDep,
) -> ExportResource:
    """Cancel a caller-owned non-terminal export."""
    try:
        export = await export_service.cancel(
            export_id=export_id,
            scope_id=principal.scope_id,
        )
    except Exception as exc:
        await _record_export_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="exports_cancel_failure_total",
            route_metric="exports_cancel",
            log_event="exports_cancel_request_failed",
            route_path="/v1/exports/{export_id}/cancel",
            activity_event_type="exports_cancel_failure",
            exc=exc,
            extra={"export_id": export_id},
        )
        raise

    try:
        await activity_store.record(
            principal=principal,
            event_type="exports_cancel_success",
            details=f"export_id={export.export_id} status={export.status}",
        )
    except Exception:
        structlog.get_logger("api").exception(
            "exports_cancel_activity_record_failed",
            export_id=export.export_id,
            status=export.status,
        )
    try:
        metrics.incr("exports_cancel_total")
        emit_request_metric(
            metrics=metrics,
            route="exports_cancel",
            status="ok",
        )
    except Exception:
        structlog.get_logger("api").exception(
            "exports_cancel_success_side_effects_failed",
            route="/v1/exports/{export_id}/cancel",
            scope_id=principal.scope_id,
            export_id=export_id,
        )
    return ExportResource.from_record(export)


async def _create_export_core(
    *,
    request: Request,
    metrics: MetricsCollector,
    export_service: ExportService,
    activity_store: ActivityStore,
    idempotency_store: IdempotencyStore,
    payload: CreateExportRequest,
    principal: Principal,
    idempotency_key: str | None,
) -> ExportResource:
    """Execute the export-create and idempotency workflow."""
    request_payload = payload.model_dump(mode="json")
    request_id = request_id_from_request(request=request)

    async def _execute() -> ExportResource:
        with metrics.timed("exports_create_ms"):
            export = await export_service.create(
                source_key=payload.source_key,
                filename=payload.filename,
                scope_id=principal.scope_id,
                request_id=request_id,
            )
        return ExportResource.from_record(export)

    async def _on_failure(exc: Exception) -> None:
        await _record_export_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="exports_create_failure_total",
            route_metric="exports_create",
            log_event="exports_create_request_failed",
            route_path="/v1/exports",
            activity_event_type="exports_create_failure",
            exc=exc,
            extra={"idempotency_key": idempotency_key},
        )

    async def _on_success(response: ExportResource) -> None:
        del response
        try:
            await activity_store.record(
                principal=principal,
                event_type="exports_create",
                details=f"request_id={request_id or 'unknown'}",
            )
            metrics.incr("exports_create_total")
            emit_request_metric(
                metrics=metrics,
                route="exports_create",
                status="ok",
            )
        except Exception:
            structlog.get_logger("api").exception(
                "exports_create_response_finalize_failed",
                route="/v1/exports",
                scope_id=principal.scope_id,
                idempotency_key=idempotency_key,
            )

    def _replay_metric() -> None:
        metrics.incr("idempotency_replays_total")

    return await run_guarded_mutation(
        route="/v1/exports",
        scope_id=principal.scope_id,
        request_payload=request_payload,
        idempotency_store=idempotency_store,
        idempotency_key=idempotency_key,
        response_model=ExportResource,
        replay_metric=_replay_metric,
        execute=_execute,
        on_failure=_on_failure,
        on_success=_on_success,
        store_response_failure_event=(
            "exports_create_idempotency_store_response_failed"
        ),
        store_response_failure_extra={
            "route": "/v1/exports",
            "scope_id": principal.scope_id,
            "idempotency_key": idempotency_key,
        },
        store_response_failure_mode="raise",
    )


async def _record_export_failure(
    *,
    metrics: MetricsCollector,
    activity_store: ActivityStore,
    principal: Principal,
    metric_name: str,
    route_metric: str,
    log_event: str,
    route_path: str,
    activity_event_type: str,
    exc: Exception,
    activity_details: str | None = None,
    extra: dict[str, object] | None = None,
) -> None:
    """Record canonical metrics, logs, and activity for export failures."""
    try:
        error_name = type(exc).__name__
        metrics.incr(metric_name)
        emit_request_metric(metrics=metrics, route=route_metric, status="error")
        log_fields: dict[str, object] = {
            "route": route_path,
            "scope_id": principal.scope_id,
            "error": error_name,
            "error_detail": error_name,
        }
        if extra:
            log_fields.update(extra)
        structlog.get_logger("api").exception(log_event, **log_fields)
        await activity_store.record(
            principal=principal,
            event_type=activity_event_type,
            details=activity_details or error_name,
        )
    except Exception:
        structlog.get_logger("api").exception(
            "exports_failure_activity_record_failed",
            route=route_path,
            scope_id=principal.scope_id,
            event_type=activity_event_type,
        )
