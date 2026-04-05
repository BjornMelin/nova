"""Transfer-domain routes for the canonical file API."""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from nova_file_api.activity import ActivityStore
from nova_file_api.dependencies import (
    ActivityStoreDep,
    IdempotencyStoreDep,
    MetricsDep,
    PrincipalDep,
    SettingsDep,
    TransferServiceDep,
)
from nova_file_api.guarded_mutation import run_guarded_mutation
from nova_file_api.models import (
    AbortUploadRequest,
    AbortUploadResponse,
    CompleteUploadRequest,
    CompleteUploadResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    PresignDownloadRequest,
    PresignDownloadResponse,
    Principal,
    SignPartsRequest,
    SignPartsResponse,
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
)
from nova_file_api.operation_ids import (
    ABORT_UPLOAD_OPERATION_ID,
    COMPLETE_UPLOAD_OPERATION_ID,
    INITIATE_UPLOAD_OPERATION_ID,
    INTROSPECT_UPLOAD_OPERATION_ID,
    PRESIGN_DOWNLOAD_OPERATION_ID,
    SIGN_UPLOAD_PARTS_OPERATION_ID,
)
from nova_file_api.routes.common import (
    COMMON_ERROR_RESPONSES,
    IDEMPOTENCY_CONFLICT_RESPONSE,
    IDEMPOTENCY_UNAVAILABLE_RESPONSE,
    IdempotencyKeyHeader,
    emit_request_metric,
    validated_idempotency_key,
)
from nova_runtime_support.metrics import MetricsCollector

transfer_router = APIRouter(
    prefix="/v1/transfers",
    tags=["transfers"],
    responses=COMMON_ERROR_RESPONSES,
)


@transfer_router.post(
    "/uploads/initiate",
    operation_id=INITIATE_UPLOAD_OPERATION_ID,
    response_model=InitiateUploadResponse,
    responses=IDEMPOTENCY_CONFLICT_RESPONSE | IDEMPOTENCY_UNAVAILABLE_RESPONSE,
)
async def initiate_upload(
    payload: InitiateUploadRequest,
    settings: SettingsDep,
    metrics: MetricsDep,
    transfer_service: TransferServiceDep,
    activity_store: ActivityStoreDep,
    idempotency_store: IdempotencyStoreDep,
    principal: PrincipalDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> InitiateUploadResponse:
    """Choose upload strategy and return presigned metadata."""
    key = validated_idempotency_key(
        settings=settings,
        idempotency_key=idempotency_key,
    )
    request_payload = payload.model_dump(mode="json")

    async def _execute() -> InitiateUploadResponse:
        with metrics.timed("uploads_initiate_ms"):
            return await transfer_service.initiate_upload(
                payload,
                principal,
            )

    async def _on_failure(exc: Exception) -> None:
        await _record_transfer_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="uploads_initiate_failure_total",
            route_metric="uploads_initiate",
            log_event="initiate_upload_request_failed",
            route_path="/v1/transfers/uploads/initiate",
            activity_event_type="uploads_initiate_failure",
            exc=exc,
        )

    async def _on_success(response: InitiateUploadResponse) -> None:
        del response
        _increment_metric_best_effort(
            metrics=metrics,
            principal=principal,
            metric_name="uploads_initiate_total",
            route_path="/v1/transfers/uploads/initiate",
            event_name="uploads_initiate_metric_increment_failed",
        )
        try:
            await activity_store.record(
                principal=principal,
                event_type="uploads_initiate",
            )
        except Exception:
            structlog.get_logger("api").exception(
                "uploads_initiate_activity_record_failed",
                route="/v1/transfers/uploads/initiate",
                scope_id=principal.scope_id,
            )
        try:
            emit_request_metric(
                metrics=metrics,
                route="uploads_initiate",
                status="ok",
            )
        except Exception:
            structlog.get_logger("api").exception(
                "uploads_initiate_metric_emit_failed",
                route="/v1/transfers/uploads/initiate",
                scope_id=principal.scope_id,
            )

    def _replay_metric() -> None:
        _increment_metric_best_effort(
            metrics=metrics,
            principal=principal,
            metric_name="idempotency_replays_total",
            route_path="/v1/transfers/uploads/initiate",
            event_name="uploads_initiate_metric_increment_failed",
        )

    return await run_guarded_mutation(
        route="/v1/transfers/uploads/initiate",
        scope_id=principal.scope_id,
        request_payload=request_payload,
        idempotency_store=idempotency_store,
        idempotency_key=key,
        response_model=InitiateUploadResponse,
        replay_metric=_replay_metric,
        execute=_execute,
        on_failure=_on_failure,
        on_success=_on_success,
        store_response_failure_event=(
            "uploads_initiate_idempotency_store_response_failed"
        ),
        store_response_failure_extra={
            "route": "/v1/transfers/uploads/initiate",
            "scope_id": principal.scope_id,
        },
        store_response_failure_mode="raise",
    )


@transfer_router.post(
    "/uploads/sign-parts",
    operation_id=SIGN_UPLOAD_PARTS_OPERATION_ID,
    response_model=SignPartsResponse,
)
async def sign_upload_parts(
    payload: SignPartsRequest,
    metrics: MetricsDep,
    transfer_service: TransferServiceDep,
    activity_store: ActivityStoreDep,
    principal: PrincipalDep,
) -> SignPartsResponse:
    """Return presigned multipart part URLs."""
    try:
        with metrics.timed("uploads_sign_parts_ms"):
            response = await transfer_service.sign_parts(
                payload,
                principal,
            )
    except Exception as exc:
        await _record_transfer_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="uploads_sign_parts_failure_total",
            route_metric="uploads_sign_parts",
            log_event="sign_parts_upload_request_failed",
            route_path="/v1/transfers/uploads/sign-parts",
            activity_event_type="uploads_sign_parts_failure",
            exc=exc,
        )
        raise

    _increment_metric_best_effort(
        metrics=metrics,
        principal=principal,
        metric_name="uploads_sign_parts_total",
        route_path="/v1/transfers/uploads/sign-parts",
        event_name="uploads_sign_parts_metric_increment_failed",
    )
    try:
        await activity_store.record(
            principal=principal,
            event_type="uploads_sign_parts",
        )
    except Exception:
        structlog.get_logger("api").exception(
            "uploads_sign_parts_activity_record_failed",
            route="/v1/transfers/uploads/sign-parts",
            scope_id=principal.scope_id,
        )
    _emit_request_metric_best_effort(
        metrics=metrics,
        principal=principal,
        route_metric="uploads_sign_parts",
        route_path="/v1/transfers/uploads/sign-parts",
        event_name="uploads_sign_parts_metric_emit_failed",
        status="ok",
    )
    return response


@transfer_router.post(
    "/uploads/introspect",
    operation_id=INTROSPECT_UPLOAD_OPERATION_ID,
    response_model=UploadIntrospectionResponse,
)
async def introspect_upload(
    payload: UploadIntrospectionRequest,
    metrics: MetricsDep,
    transfer_service: TransferServiceDep,
    activity_store: ActivityStoreDep,
    principal: PrincipalDep,
) -> UploadIntrospectionResponse:
    """Return uploaded multipart part state for resume flows.

    Args:
        payload: Multipart introspection input payload.
        metrics: Request-scoped metrics collector dependency.
        transfer_service: Transfer domain service dependency.
        activity_store: Activity persistence dependency.
        principal: Authenticated caller principal.

    Returns:
        UploadIntrospectionResponse: Multipart state for resume operations.
    """
    try:
        with metrics.timed("uploads_introspect_ms"):
            response = await transfer_service.introspect_upload(
                payload,
                principal,
            )
    except Exception as exc:
        await _record_transfer_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="uploads_introspect_failure_total",
            route_metric="uploads_introspect",
            log_event="introspect_upload_request_failed",
            route_path="/v1/transfers/uploads/introspect",
            activity_event_type="uploads_introspect_failure",
            exc=exc,
        )
        raise

    _increment_metric_best_effort(
        metrics=metrics,
        principal=principal,
        metric_name="uploads_introspect_total",
        route_path="/v1/transfers/uploads/introspect",
        event_name="uploads_introspect_metric_increment_failed",
    )
    try:
        await activity_store.record(
            principal=principal,
            event_type="uploads_introspect",
        )
    except Exception:
        structlog.get_logger("api").exception(
            "uploads_introspect_activity_record_failed",
            route="/v1/transfers/uploads/introspect",
            scope_id=principal.scope_id,
        )
    _emit_request_metric_best_effort(
        metrics=metrics,
        principal=principal,
        route_metric="uploads_introspect",
        route_path="/v1/transfers/uploads/introspect",
        event_name="uploads_introspect_metric_emit_failed",
        status="ok",
    )
    return response


@transfer_router.post(
    "/uploads/complete",
    operation_id=COMPLETE_UPLOAD_OPERATION_ID,
    response_model=CompleteUploadResponse,
)
async def complete_upload(
    payload: CompleteUploadRequest,
    metrics: MetricsDep,
    transfer_service: TransferServiceDep,
    activity_store: ActivityStoreDep,
    principal: PrincipalDep,
) -> CompleteUploadResponse:
    """Complete multipart upload."""
    try:
        with metrics.timed("uploads_complete_ms"):
            response = await transfer_service.complete_upload(
                payload,
                principal,
            )
    except Exception as exc:
        await _record_transfer_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="uploads_complete_failure_total",
            route_metric="uploads_complete",
            log_event="complete_upload_request_failed",
            route_path="/v1/transfers/uploads/complete",
            activity_event_type="uploads_complete_failure",
            exc=exc,
        )
        raise

    _increment_metric_best_effort(
        metrics=metrics,
        principal=principal,
        metric_name="uploads_complete_total",
        route_path="/v1/transfers/uploads/complete",
        event_name="uploads_complete_metric_increment_failed",
    )
    try:
        await activity_store.record(
            principal=principal,
            event_type="uploads_complete",
        )
    except Exception:
        structlog.get_logger("api").exception(
            "uploads_complete_activity_record_failed",
            route="/v1/transfers/uploads/complete",
            scope_id=principal.scope_id,
        )
    _emit_request_metric_best_effort(
        metrics=metrics,
        principal=principal,
        route_metric="uploads_complete",
        route_path="/v1/transfers/uploads/complete",
        event_name="uploads_complete_metric_emit_failed",
        status="ok",
    )
    return response


@transfer_router.post(
    "/uploads/abort",
    operation_id=ABORT_UPLOAD_OPERATION_ID,
    response_model=AbortUploadResponse,
)
async def abort_upload(
    payload: AbortUploadRequest,
    metrics: MetricsDep,
    transfer_service: TransferServiceDep,
    activity_store: ActivityStoreDep,
    principal: PrincipalDep,
) -> AbortUploadResponse:
    """Abort multipart upload."""
    try:
        with metrics.timed("uploads_abort_ms"):
            response = await transfer_service.abort_upload(
                payload,
                principal,
            )
    except Exception as exc:
        await _record_transfer_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="uploads_abort_failure_total",
            route_metric="uploads_abort",
            log_event="abort_upload_request_failed",
            route_path="/v1/transfers/uploads/abort",
            activity_event_type="uploads_abort_failure",
            exc=exc,
        )
        raise

    _increment_metric_best_effort(
        metrics=metrics,
        principal=principal,
        metric_name="uploads_abort_total",
        route_path="/v1/transfers/uploads/abort",
        event_name="uploads_abort_metric_increment_failed",
    )
    try:
        await activity_store.record(
            principal=principal,
            event_type="uploads_abort",
        )
    except Exception:
        structlog.get_logger("api").exception(
            "uploads_abort_activity_record_failed",
            route="/v1/transfers/uploads/abort",
            scope_id=principal.scope_id,
        )
    _emit_request_metric_best_effort(
        metrics=metrics,
        principal=principal,
        route_metric="uploads_abort",
        route_path="/v1/transfers/uploads/abort",
        event_name="uploads_abort_metric_emit_failed",
        status="ok",
    )
    return response


@transfer_router.post(
    "/downloads/presign",
    operation_id=PRESIGN_DOWNLOAD_OPERATION_ID,
    response_model=PresignDownloadResponse,
)
async def presign_download(
    payload: PresignDownloadRequest,
    metrics: MetricsDep,
    transfer_service: TransferServiceDep,
    activity_store: ActivityStoreDep,
    principal: PrincipalDep,
) -> PresignDownloadResponse:
    """Issue presigned GET URL for caller-scoped key."""
    try:
        with metrics.timed("downloads_presign_ms"):
            response = await transfer_service.presign_download(
                payload,
                principal,
            )
    except Exception as exc:
        await _record_transfer_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="downloads_presign_failure_total",
            route_metric="downloads_presign",
            log_event="presign_download_request_failed",
            route_path="/v1/transfers/downloads/presign",
            activity_event_type="downloads_presign_failure",
            exc=exc,
        )
        raise

    _increment_metric_best_effort(
        metrics=metrics,
        principal=principal,
        metric_name="downloads_presign_total",
        route_path="/v1/transfers/downloads/presign",
        event_name="downloads_presign_metric_increment_failed",
    )
    try:
        await activity_store.record(
            principal=principal,
            event_type="downloads_presign",
        )
    except Exception:
        structlog.get_logger("api").exception(
            "downloads_presign_activity_record_failed",
            route="/v1/transfers/downloads/presign",
            scope_id=principal.scope_id,
        )
    _emit_request_metric_best_effort(
        metrics=metrics,
        principal=principal,
        route_metric="downloads_presign",
        route_path="/v1/transfers/downloads/presign",
        event_name="downloads_presign_metric_emit_failed",
        status="ok",
    )
    return response


async def _record_transfer_failure(
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
) -> None:
    """Record canonical metrics, logs, and activity for transfer failures."""
    _emit_request_metric_best_effort(
        metrics=metrics,
        principal=principal,
        route_metric=route_metric,
        route_path=route_path,
        event_name="transfer_failure_metric_emit_failed",
        status="error",
        counter_metric=metric_name,
    )
    structlog.get_logger("api").exception(
        log_event,
        route=route_path,
        scope_id=principal.scope_id,
        error=type(exc).__name__,
        error_code="transfer_failure",
    )
    try:
        await activity_store.record(
            principal=principal,
            event_type=activity_event_type,
            details=type(exc).__name__,
        )
    except Exception:
        structlog.get_logger("api").exception(
            "transfer_failure_activity_record_failed",
            route=route_path,
            scope_id=principal.scope_id,
            event_type=activity_event_type,
        )


def _emit_request_metric_best_effort(
    *,
    metrics: MetricsCollector,
    principal: Principal,
    route_metric: str,
    route_path: str,
    event_name: str,
    status: str,
    counter_metric: str | None = None,
) -> None:
    """Emit request metrics without failing completed request handlers."""
    try:
        if counter_metric is not None:
            metrics.incr(counter_metric)
        emit_request_metric(
            metrics=metrics,
            route=route_metric,
            status=status,
        )
    except Exception:
        structlog.get_logger("api").exception(
            event_name,
            route=route_path,
            scope_id=principal.scope_id,
            status=status,
            counter_metric=counter_metric,
        )


def _increment_metric_best_effort(
    *,
    metrics: MetricsCollector,
    principal: Principal,
    metric_name: str,
    route_path: str,
    event_name: str,
) -> None:
    """Increment counters without failing completed request handlers."""
    try:
        metrics.incr(metric_name)
    except Exception:
        structlog.get_logger("api").exception(
            event_name,
            route=route_path,
            scope_id=principal.scope_id,
            metric_name=metric_name,
        )
