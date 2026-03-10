"""Transfer-domain routes for the canonical file API."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter

from nova_file_api.dependencies import RequestContext, RequestContextDep
from nova_file_api.errors import idempotency_conflict
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
)
from nova_file_api.operation_ids import (
    ABORT_UPLOAD_OPERATION_ID,
    COMPLETE_UPLOAD_OPERATION_ID,
    INITIATE_UPLOAD_OPERATION_ID,
    PRESIGN_DOWNLOAD_OPERATION_ID,
    SIGN_UPLOAD_PARTS_OPERATION_ID,
)
from nova_file_api.routes.common import (
    IdempotencyKeyHeader,
    emit_request_metric,
    validated_idempotency_key,
)

transfer_router = APIRouter(prefix="/v1/transfers", tags=["transfers"])


@transfer_router.post(
    "/uploads/initiate",
    operation_id=INITIATE_UPLOAD_OPERATION_ID,
    response_model=InitiateUploadResponse,
)
async def initiate_upload(
    payload: InitiateUploadRequest,
    context: RequestContextDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> InitiateUploadResponse:
    """
    Determine the upload strategy and provide presigned metadata and instructions for starting an upload.
    
    If an idempotency key is provided, the request may be replayed, claimed for deduplication, and the final response stored for future replays; metrics and activity events are emitted on a best-effort basis.
    
    Parameters:
        idempotency_key (IdempotencyKeyHeader, optional): Idempotency key used to enable replay and deduplication of this request. If omitted, idempotency semantics are not applied.
    
    Returns:
        InitiateUploadResponse: Presigned upload metadata and client instructions required to perform the upload.
    """
    container = context.container
    principal = await context.authenticate(session_id=payload.session_id)
    key = validated_idempotency_key(
        container=container,
        idempotency_key=idempotency_key,
    )
    request_payload = payload.model_dump(mode="json")
    claimed_idempotency = False

    if key is not None:
        replay = await container.idempotency_store.load_response(
            route="/v1/transfers/uploads/initiate",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
        )
        if replay is not None:
            _increment_metric_best_effort(
                container=container,
                principal=principal,
                metric_name="idempotency_replays_total",
                route_path="/v1/transfers/uploads/initiate",
                event_name="uploads_initiate_metric_increment_failed",
            )
            return InitiateUploadResponse.model_validate(replay)

        claimed_idempotency = await container.idempotency_store.claim_request(
            route="/v1/transfers/uploads/initiate",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
        )
        if not claimed_idempotency:
            replay = await container.idempotency_store.load_response(
                route="/v1/transfers/uploads/initiate",
                scope_id=principal.scope_id,
                idempotency_key=key,
                request_payload=request_payload,
            )
            if replay is not None:
                _increment_metric_best_effort(
                    container=container,
                    principal=principal,
                    metric_name="idempotency_replays_total",
                    route_path="/v1/transfers/uploads/initiate",
                    event_name="uploads_initiate_metric_increment_failed",
                )
                return InitiateUploadResponse.model_validate(replay)
            raise idempotency_conflict(
                "idempotency request is already in progress"
            )

    try:
        with container.metrics.timed("uploads_initiate_ms"):
            response = await container.transfer_service.initiate_upload(
                payload,
                principal,
            )
    except Exception as exc:
        await _record_transfer_failure(
            context=context,
            principal=principal,
            metric_name="uploads_initiate_failure_total",
            route_metric="uploads_initiate",
            log_event="initiate_upload_request_failed",
            route_path="/v1/transfers/uploads/initiate",
            activity_event_type="uploads_initiate_failure",
            exc=exc,
        )
        if key is not None and claimed_idempotency:
            await container.idempotency_store.discard_claim(
                route="/v1/transfers/uploads/initiate",
                scope_id=principal.scope_id,
                idempotency_key=key,
            )
        raise

    if key is not None:
        try:
            await container.idempotency_store.store_response(
                route="/v1/transfers/uploads/initiate",
                scope_id=principal.scope_id,
                idempotency_key=key,
                request_payload=request_payload,
                response_payload=response.model_dump(mode="json"),
            )
        except Exception:
            if claimed_idempotency:
                await container.idempotency_store.discard_claim(
                    route="/v1/transfers/uploads/initiate",
                    scope_id=principal.scope_id,
                    idempotency_key=key,
                )
            structlog.get_logger("api").exception(
                "uploads_initiate_idempotency_store_response_failed",
                route="/v1/transfers/uploads/initiate",
                scope_id=principal.scope_id,
            )
            raise

    _increment_metric_best_effort(
        container=container,
        principal=principal,
        metric_name="uploads_initiate_total",
        route_path="/v1/transfers/uploads/initiate",
        event_name="uploads_initiate_metric_increment_failed",
    )
    try:
        await container.activity_store.record(
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
            container=container,
            route="uploads_initiate",
            status="ok",
        )
    except Exception:
        structlog.get_logger("api").exception(
            "uploads_initiate_metric_emit_failed",
            route="/v1/transfers/uploads/initiate",
            scope_id=principal.scope_id,
        )
    return response


@transfer_router.post(
    "/uploads/sign-parts",
    operation_id=SIGN_UPLOAD_PARTS_OPERATION_ID,
    response_model=SignPartsResponse,
)
async def sign_upload_parts(
    payload: SignPartsRequest,
    context: RequestContextDep,
) -> SignPartsResponse:
    """
    Generate presigned URLs for multipart upload parts.
    
    Returns:
        SignPartsResponse: Presigned part URLs along with multipart upload identifiers and related metadata.
    """
    container = context.container
    principal = await context.authenticate(session_id=payload.session_id)

    try:
        with container.metrics.timed("uploads_sign_parts_ms"):
            response = await container.transfer_service.sign_parts(
                payload,
                principal,
            )
    except Exception as exc:
        await _record_transfer_failure(
            context=context,
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
        container=container,
        principal=principal,
        metric_name="uploads_sign_parts_total",
        route_path="/v1/transfers/uploads/sign-parts",
        event_name="uploads_sign_parts_metric_increment_failed",
    )
    try:
        await container.activity_store.record(
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
        container=container,
        principal=principal,
        route_metric="uploads_sign_parts",
        route_path="/v1/transfers/uploads/sign-parts",
        event_name="uploads_sign_parts_metric_emit_failed",
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
    context: RequestContextDep,
) -> CompleteUploadResponse:
    """
    Complete a multipart upload and return details about the completed transfer.
    
    Returns:
        response (CompleteUploadResponse): Details about the completed upload.
    """
    container = context.container
    principal = await context.authenticate(session_id=payload.session_id)

    try:
        with container.metrics.timed("uploads_complete_ms"):
            response = await container.transfer_service.complete_upload(
                payload,
                principal,
            )
    except Exception as exc:
        await _record_transfer_failure(
            context=context,
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
        container=container,
        principal=principal,
        metric_name="uploads_complete_total",
        route_path="/v1/transfers/uploads/complete",
        event_name="uploads_complete_metric_increment_failed",
    )
    try:
        await container.activity_store.record(
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
        container=container,
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
    context: RequestContextDep,
) -> AbortUploadResponse:
    """
    Abort an in-progress multipart upload.
    
    Attempts to abort the multipart upload identified by the request payload; on success it records best-effort metrics and an activity event describing the abort.
    
    Returns:
        An AbortUploadResponse describing the result of the abort operation.
    """
    container = context.container
    principal = await context.authenticate(session_id=payload.session_id)

    try:
        with container.metrics.timed("uploads_abort_ms"):
            response = await container.transfer_service.abort_upload(
                payload,
                principal,
            )
    except Exception as exc:
        await _record_transfer_failure(
            context=context,
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
        container=container,
        principal=principal,
        metric_name="uploads_abort_total",
        route_path="/v1/transfers/uploads/abort",
        event_name="uploads_abort_metric_increment_failed",
    )
    try:
        await container.activity_store.record(
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
        container=container,
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
    context: RequestContextDep,
) -> PresignDownloadResponse:
    """
    Issue a presigned GET URL scoped to the requesting principal.
    
    Performs the presign operation for the provided request and attempts to emit request metrics and record an activity event; failures in metric or activity recording are best-effort and do not change the operation result. On presign operation failure, transfer failure metrics and an activity attempt are recorded before the exception is propagated.
    
    Returns:
        PresignDownloadResponse: Object containing the presigned GET URL and any associated metadata required to perform the download.
    """
    container = context.container
    principal = await context.authenticate(session_id=payload.session_id)

    try:
        with container.metrics.timed("downloads_presign_ms"):
            response = await container.transfer_service.presign_download(
                payload,
                principal,
            )
    except Exception as exc:
        await _record_transfer_failure(
            context=context,
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
        container=container,
        principal=principal,
        metric_name="downloads_presign_total",
        route_path="/v1/transfers/downloads/presign",
        event_name="downloads_presign_metric_increment_failed",
    )
    try:
        await container.activity_store.record(
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
        container=container,
        principal=principal,
        route_metric="downloads_presign",
        route_path="/v1/transfers/downloads/presign",
        event_name="downloads_presign_metric_emit_failed",
        status="ok",
    )
    return response


async def _record_transfer_failure(
    *,
    context: RequestContext,
    principal: Principal,
    metric_name: str,
    route_metric: str,
    log_event: str,
    route_path: str,
    activity_event_type: str,
    exc: Exception,
) -> None:
    """
    Record transfer failure metrics, emit a structured log entry, and attempt to record an activity event.
    
    This helper emits a failure metric (best-effort), logs the provided exception and context (route and principal scope), and then attempts to record an activity event describing the failure; if activity recording fails, that failure is logged but not raised.
    
    Parameters:
        context (RequestContext): Request-scoped container and services used to emit metrics and record activity.
        principal (Principal): Authenticated principal associated with the request; used for scope and activity recording.
        metric_name (str): Name of the counter metric to increment for the failure.
        route_metric (str): Route identifier used when emitting the route-level metric.
        log_event (str): Message/event name to include in the structured exception log.
        route_path (str): API route path used in logs and metrics for context.
        activity_event_type (str): Activity event type name to record in the activity store.
        exc (Exception): The exception instance that caused the transfer failure.
    """
    container = context.container
    _emit_request_metric_best_effort(
        container=container,
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
        await container.activity_store.record(
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
    container: Any,
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
            container.metrics.incr(counter_metric)
        emit_request_metric(
            container=container,
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
    container: Any,
    principal: Principal,
    metric_name: str,
    route_path: str,
    event_name: str,
) -> None:
    """Increment counters without failing completed request handlers."""
    try:
        container.metrics.incr(metric_name)
    except Exception:
        structlog.get_logger("api").exception(
            event_name,
            route=route_path,
            scope_id=principal.scope_id,
            metric_name=metric_name,
        )