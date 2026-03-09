"""Transfer-domain routes for the canonical file API."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Header

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
from nova_file_api.routes.common import (
    emit_request_metric,
    validated_idempotency_key,
)

transfer_router = APIRouter(prefix="/v1/transfers", tags=["transfers"])


@transfer_router.post(
    "/uploads/initiate",
    response_model=InitiateUploadResponse,
)
async def initiate_upload(
    payload: InitiateUploadRequest,
    context: RequestContextDep,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
) -> InitiateUploadResponse:
    """Choose upload strategy and return presigned metadata."""
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
            response = await context.run_blocking(
                container.transfer_service.initiate_upload,
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
        await context.run_blocking(
            container.activity_store.record,
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
    response_model=SignPartsResponse,
)
async def sign_upload_parts(
    payload: SignPartsRequest,
    context: RequestContextDep,
) -> SignPartsResponse:
    """Return presigned multipart part URLs."""
    container = context.container
    principal = await context.authenticate(session_id=payload.session_id)

    try:
        with container.metrics.timed("uploads_sign_parts_ms"):
            response = await context.run_blocking(
                container.transfer_service.sign_parts,
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
        await context.run_blocking(
            container.activity_store.record,
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
    response_model=CompleteUploadResponse,
)
async def complete_upload(
    payload: CompleteUploadRequest,
    context: RequestContextDep,
) -> CompleteUploadResponse:
    """Complete multipart upload."""
    container = context.container
    principal = await context.authenticate(session_id=payload.session_id)

    try:
        with container.metrics.timed("uploads_complete_ms"):
            response = await context.run_blocking(
                container.transfer_service.complete_upload,
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
        await context.run_blocking(
            container.activity_store.record,
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
    response_model=AbortUploadResponse,
)
async def abort_upload(
    payload: AbortUploadRequest,
    context: RequestContextDep,
) -> AbortUploadResponse:
    """Abort multipart upload."""
    container = context.container
    principal = await context.authenticate(session_id=payload.session_id)

    try:
        with container.metrics.timed("uploads_abort_ms"):
            response = await context.run_blocking(
                container.transfer_service.abort_upload,
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
        await context.run_blocking(
            container.activity_store.record,
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
    response_model=PresignDownloadResponse,
)
async def presign_download(
    payload: PresignDownloadRequest,
    context: RequestContextDep,
) -> PresignDownloadResponse:
    """Issue presigned GET URL for caller-scoped key."""
    container = context.container
    principal = await context.authenticate(session_id=payload.session_id)

    try:
        with container.metrics.timed("downloads_presign_ms"):
            response = await context.run_blocking(
                container.transfer_service.presign_download,
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
        await context.run_blocking(
            container.activity_store.record,
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
    """Record canonical metrics, logs, and activity for transfer failures."""
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
        await context.run_blocking(
            container.activity_store.record,
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
