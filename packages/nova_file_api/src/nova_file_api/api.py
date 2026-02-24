"""FastAPI routers for transfer API and operational endpoints."""

from __future__ import annotations

from hmac import compare_digest

import structlog
from fastapi import APIRouter, Header, Request
from starlette.concurrency import run_in_threadpool

from nova_file_api.container import AppContainer
from nova_file_api.dependencies import get_container
from nova_file_api.errors import (
    forbidden,
    idempotency_conflict,
    invalid_request,
)
from nova_file_api.models import (
    AbortUploadRequest,
    AbortUploadResponse,
    AuthMode,
    CompleteUploadRequest,
    CompleteUploadResponse,
    EnqueueJobRequest,
    EnqueueJobResponse,
    HealthResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    JobCancelResponse,
    JobResultUpdateRequest,
    JobResultUpdateResponse,
    JobStatusResponse,
    MetricsSummaryResponse,
    PresignDownloadRequest,
    PresignDownloadResponse,
    ReadinessResponse,
    SignPartsRequest,
    SignPartsResponse,
)

transfer_router = APIRouter(prefix="/api/transfers", tags=["transfers"])
jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])
ops_router = APIRouter(tags=["ops"])
_WORKER_TOKEN_NOT_CONFIGURED = "worker update token not configured"


@transfer_router.post(
    "/uploads/initiate", response_model=InitiateUploadResponse
)
async def initiate_upload(
    payload: InitiateUploadRequest,
    request: Request,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
) -> InitiateUploadResponse:
    """Choose upload strategy and return presigned metadata."""
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request,
        session_id=payload.session_id,
    )
    key = _validated_idempotency_key(
        container=container,
        idempotency_key=idempotency_key,
    )
    request_payload = payload.model_dump(mode="json")
    claimed_idempotency = False
    if key is not None:
        replay = await container.idempotency_store.load_response(
            route="/api/transfers/uploads/initiate",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
        )
        if replay is not None:
            container.metrics.incr("idempotency_replays_total")
            return InitiateUploadResponse.model_validate(replay)
        claimed_idempotency = await container.idempotency_store.claim_request(
            route="/api/transfers/uploads/initiate",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
        )
        if not claimed_idempotency:
            replay = await container.idempotency_store.load_response(
                route="/api/transfers/uploads/initiate",
                scope_id=principal.scope_id,
                idempotency_key=key,
                request_payload=request_payload,
            )
            if replay is not None:
                container.metrics.incr("idempotency_replays_total")
                return InitiateUploadResponse.model_validate(replay)
            raise idempotency_conflict(
                "idempotency request is already in progress"
            )

    try:
        with container.metrics.timed("uploads_initiate_ms"):
            response = await run_in_threadpool(
                container.transfer_service.initiate_upload,
                payload,
                principal,
            )
    except Exception:
        container.metrics.incr("uploads_initiate_errors")
        _emit_request_metric(
            container=container, route="uploads_initiate", status="error"
        )
        await run_in_threadpool(
            container.activity_store.record,
            principal=principal,
            event_type="uploads_initiate_failure",
        )
        if key is not None and claimed_idempotency:
            await container.idempotency_store.discard_claim(
                route="/api/transfers/uploads/initiate",
                scope_id=principal.scope_id,
                idempotency_key=key,
            )
        raise

    if key is not None:
        await container.idempotency_store.store_response(
            route="/api/transfers/uploads/initiate",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
            response_payload=response.model_dump(mode="json"),
        )

    container.metrics.incr("uploads_initiate_total")
    await run_in_threadpool(
        container.activity_store.record,
        principal=principal,
        event_type="uploads_initiate",
    )
    _emit_request_metric(
        container=container, route="uploads_initiate", status="ok"
    )
    return response


@transfer_router.post("/uploads/sign-parts", response_model=SignPartsResponse)
async def sign_parts(
    payload: SignPartsRequest,
    request: Request,
) -> SignPartsResponse:
    """Return presigned multipart part URLs."""
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request,
        session_id=payload.session_id,
    )

    try:
        with container.metrics.timed("uploads_sign_parts_ms"):
            response = await run_in_threadpool(
                container.transfer_service.sign_parts,
                payload,
                principal,
            )
    except Exception as exc:
        container.metrics.incr("uploads_sign_parts_failure_total")
        _emit_request_metric(
            container=container, route="uploads_sign_parts", status="error"
        )
        log = structlog.get_logger("api")
        log.exception(
            "sign_parts_upload_request_failed",
            route="/api/transfers/uploads/sign-parts",
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await run_in_threadpool(
            container.activity_store.record,
            principal=principal,
            event_type="uploads_sign_parts_failure",
            details=str(exc),
        )
        raise

    container.metrics.incr("uploads_sign_parts_total")
    await run_in_threadpool(
        container.activity_store.record,
        principal=principal,
        event_type="uploads_sign_parts",
    )
    _emit_request_metric(
        container=container, route="uploads_sign_parts", status="ok"
    )
    return response


@transfer_router.post(
    "/uploads/complete", response_model=CompleteUploadResponse
)
async def complete_upload(
    payload: CompleteUploadRequest,
    request: Request,
) -> CompleteUploadResponse:
    """Complete multipart upload."""
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request,
        session_id=payload.session_id,
    )

    try:
        with container.metrics.timed("uploads_complete_ms"):
            response = await run_in_threadpool(
                container.transfer_service.complete_upload,
                payload,
                principal,
            )
    except Exception as exc:
        container.metrics.incr("uploads_complete_failure_total")
        _emit_request_metric(
            container=container, route="uploads_complete", status="error"
        )
        log = structlog.get_logger("api")
        log.exception(
            "complete_upload_request_failed",
            route="/api/transfers/uploads/complete",
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await run_in_threadpool(
            container.activity_store.record,
            principal=principal,
            event_type="uploads_complete_failure",
            details=str(exc),
        )
        raise

    container.metrics.incr("uploads_complete_total")
    await run_in_threadpool(
        container.activity_store.record,
        principal=principal,
        event_type="uploads_complete",
    )
    _emit_request_metric(
        container=container, route="uploads_complete", status="ok"
    )
    return response


@transfer_router.post("/uploads/abort", response_model=AbortUploadResponse)
async def abort_upload(
    payload: AbortUploadRequest,
    request: Request,
) -> AbortUploadResponse:
    """Abort multipart upload."""
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request,
        session_id=payload.session_id,
    )

    try:
        with container.metrics.timed("uploads_abort_ms"):
            response = await run_in_threadpool(
                container.transfer_service.abort_upload,
                payload,
                principal,
            )
    except Exception as exc:
        container.metrics.incr("uploads_abort_failure_total")
        _emit_request_metric(
            container=container, route="uploads_abort", status="error"
        )
        log = structlog.get_logger("api")
        log.exception(
            "abort_upload_request_failed",
            route="/api/transfers/uploads/abort",
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await run_in_threadpool(
            container.activity_store.record,
            principal=principal,
            event_type="uploads_abort_failure",
            details=str(exc),
        )
        raise

    container.metrics.incr("uploads_abort_total")
    await run_in_threadpool(
        container.activity_store.record,
        principal=principal,
        event_type="uploads_abort",
    )
    _emit_request_metric(
        container=container, route="uploads_abort", status="ok"
    )
    return response


@transfer_router.post(
    "/downloads/presign", response_model=PresignDownloadResponse
)
async def presign_download(
    payload: PresignDownloadRequest,
    request: Request,
) -> PresignDownloadResponse:
    """Issue presigned GET URL for caller-scoped key."""
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request,
        session_id=payload.session_id,
    )

    try:
        with container.metrics.timed("downloads_presign_ms"):
            response = await run_in_threadpool(
                container.transfer_service.presign_download,
                payload,
                principal,
            )
    except Exception as exc:
        container.metrics.incr("downloads_presign_failure_total")
        _emit_request_metric(
            container=container, route="downloads_presign", status="error"
        )
        log = structlog.get_logger("api")
        log.exception(
            "presign_download_request_failed",
            route="/api/transfers/downloads/presign",
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await run_in_threadpool(
            container.activity_store.record,
            principal=principal,
            event_type="downloads_presign_failure",
            details=str(exc),
        )
        raise

    container.metrics.incr("downloads_presign_total")
    await run_in_threadpool(
        container.activity_store.record,
        principal=principal,
        event_type="downloads_presign",
    )
    _emit_request_metric(
        container=container, route="downloads_presign", status="ok"
    )
    return response


@jobs_router.post("/enqueue", response_model=EnqueueJobResponse)
async def enqueue_job(
    payload: EnqueueJobRequest,
    request: Request,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
) -> EnqueueJobResponse:
    """Enqueue async processing job and return job id."""
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request,
        session_id=payload.session_id,
    )

    if not container.settings.jobs_enabled:
        raise forbidden("jobs API is disabled")
    key = _validated_idempotency_key(
        container=container,
        idempotency_key=idempotency_key,
    )
    request_payload = payload.model_dump(mode="json")
    claimed_idempotency = False
    if key is not None:
        replay = await container.idempotency_store.load_response(
            route="/api/jobs/enqueue",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
        )
        if replay is not None:
            container.metrics.incr("idempotency_replays_total")
            return EnqueueJobResponse.model_validate(replay)
        claimed_idempotency = await container.idempotency_store.claim_request(
            route="/api/jobs/enqueue",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
        )
        if not claimed_idempotency:
            replay = await container.idempotency_store.load_response(
                route="/api/jobs/enqueue",
                scope_id=principal.scope_id,
                idempotency_key=key,
                request_payload=request_payload,
            )
            if replay is not None:
                container.metrics.incr("idempotency_replays_total")
                return EnqueueJobResponse.model_validate(replay)
            raise idempotency_conflict(
                "idempotency request is already in progress"
            )

    try:
        with container.metrics.timed("jobs_enqueue_ms"):
            job = await run_in_threadpool(
                container.job_service.enqueue,
                job_type=payload.job_type,
                payload=payload.payload,
                scope_id=principal.scope_id,
            )
    except Exception as exc:
        container.metrics.incr("jobs_enqueue_failure_total")
        _emit_request_metric(
            container=container, route="jobs_enqueue", status="error"
        )
        log = structlog.get_logger("api")
        log.exception(
            "jobs_enqueue_request_failed",
            route="/api/jobs/enqueue",
            scope_id=principal.scope_id,
            idempotency_key=key,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await run_in_threadpool(
            container.activity_store.record,
            principal=principal,
            event_type="jobs_enqueue_failure",
            details=str(exc),
        )
        if key is not None and claimed_idempotency:
            await container.idempotency_store.discard_claim(
                route="/api/jobs/enqueue",
                scope_id=principal.scope_id,
                idempotency_key=key,
            )
        raise

    response = EnqueueJobResponse(job_id=job.job_id, status=job.status)
    if key is not None:
        await container.idempotency_store.store_response(
            route="/api/jobs/enqueue",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
            response_payload=response.model_dump(mode="json"),
        )
    await run_in_threadpool(
        container.activity_store.record,
        principal=principal,
        event_type="jobs_enqueue",
    )
    _emit_request_metric(container=container, route="jobs_enqueue", status="ok")
    return response


@jobs_router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, request: Request) -> JobStatusResponse:
    """Return status for caller-owned job."""
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request,
        session_id=None,
    )
    try:
        job = await run_in_threadpool(
            container.job_service.get,
            job_id=job_id,
            scope_id=principal.scope_id,
        )
    except Exception as exc:
        container.metrics.incr("jobs_status_failure_total")
        _emit_request_metric(
            container=container, route="jobs_status", status="error"
        )
        log = structlog.get_logger("api")
        log.exception(
            "jobs_status_request_failed",
            route="/api/jobs/{job_id}",
            job_id=job_id,
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await run_in_threadpool(
            container.activity_store.record,
            principal=principal,
            event_type="jobs_status_failure",
            details=str(exc),
        )
        raise
    _emit_request_metric(container=container, route="jobs_status", status="ok")
    return JobStatusResponse(job=job)


@jobs_router.post("/{job_id}/cancel", response_model=JobCancelResponse)
async def cancel_job(job_id: str, request: Request) -> JobCancelResponse:
    """Cancel caller-owned non-terminal job."""
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request,
        session_id=None,
    )
    try:
        job = await run_in_threadpool(
            container.job_service.cancel,
            job_id=job_id,
            scope_id=principal.scope_id,
        )
    except Exception as exc:
        container.metrics.incr("jobs_cancel_failure_total")
        _emit_request_metric(
            container=container, route="jobs_cancel", status="error"
        )
        log = structlog.get_logger("api")
        log.exception(
            "jobs_cancel_request_failed",
            route="/api/jobs/{job_id}/cancel",
            job_id=job_id,
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await run_in_threadpool(
            container.activity_store.record,
            principal=principal,
            event_type="jobs_cancel_failure",
            details=str(exc),
        )
        raise
    _emit_request_metric(container=container, route="jobs_cancel", status="ok")
    return JobCancelResponse(job_id=job.job_id, status=job.status)


@jobs_router.post(
    "/{job_id}/result",
    response_model=JobResultUpdateResponse,
)
async def update_job_result(
    job_id: str,
    payload: JobResultUpdateRequest,
    request: Request,
    worker_token: str | None = Header(default=None, alias="X-Worker-Token"),
) -> JobResultUpdateResponse:
    """Update job status/result from trusted worker-side processing."""
    container = get_container(request)
    if not container.settings.jobs_enabled:
        raise forbidden("jobs API is disabled")
    _validate_worker_update_token(
        container=container,
        worker_token=worker_token,
    )
    try:
        job = await run_in_threadpool(
            container.job_service.update_result,
            job_id=job_id,
            status=payload.status,
            result=payload.result,
            error=payload.error,
        )
    except Exception as exc:
        container.metrics.incr("jobs_result_update_failure_total")
        _emit_request_metric(
            container=container, route="jobs_result_update", status="error"
        )
        log = structlog.get_logger("api")
        log.exception(
            "jobs_result_update_request_failed",
            route="/api/jobs/{job_id}/result",
            job_id=job_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        raise
    _emit_request_metric(
        container=container, route="jobs_result_update", status="ok"
    )
    return JobResultUpdateResponse(
        job_id=job.job_id,
        status=job.status,
        updated_at=job.updated_at,
    )


@ops_router.get("/metrics/summary", response_model=MetricsSummaryResponse)
async def metrics_summary(request: Request) -> MetricsSummaryResponse:
    """Return low-cardinality metrics summary for dashboards."""
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request,
        session_id=None,
    )

    if (
        container.settings.auth_mode != AuthMode.SAME_ORIGIN
        and "metrics:read" not in principal.permissions
    ):
        raise forbidden("missing metrics:read permission")

    return MetricsSummaryResponse(
        counters=container.metrics.counters_snapshot(),
        latencies_ms=container.metrics.latency_snapshot(),
        activity=await run_in_threadpool(container.activity_store.summary),
    )


@ops_router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Return liveness status."""
    return HealthResponse(ok=True)


@ops_router.get("/readyz", response_model=ReadinessResponse)
async def readyz(request: Request) -> ReadinessResponse:
    """Return readiness checks for critical dependencies."""
    container = get_container(request)
    logger = structlog.get_logger("api")
    try:
        shared_cache = await container.shared_cache.ping()
    except Exception:
        logger.exception(
            "readyz_shared_cache_ping_failed",
            route="/readyz",
        )
        shared_cache = False
    checks = {
        "bucket_configured": bool(
            container.settings.file_transfer_bucket.strip()
        ),
        "shared_cache": shared_cache,
    }
    return ReadinessResponse(ok=all(checks.values()), checks=checks)


def _emit_request_metric(
    *,
    container: AppContainer,
    route: str,
    status: str,
) -> None:
    container.metrics.emit_emf(
        metric_name="requests_total",
        value=1,
        unit="Count",
        dimensions={"route": route, "status": status},
    )


def _validated_idempotency_key(
    *,
    container: AppContainer,
    idempotency_key: str | None,
) -> str | None:
    """Validate Idempotency-Key header for protected mutation routes."""
    if not container.settings.idempotency_enabled:
        return None
    if idempotency_key is None:
        return None
    if not idempotency_key.strip():
        raise invalid_request("invalid Idempotency-Key header")
    return idempotency_key.strip()


def _validate_worker_update_token(
    *,
    container: AppContainer,
    worker_token: str | None,
) -> None:
    """Validate worker update token when configured."""
    expected = container.settings.jobs_worker_update_token
    expected_token = (
        expected.get_secret_value() if expected is not None else None
    )
    if expected_token is None or not expected_token.strip():
        if container.settings.environment.lower() in {"prod", "production"}:
            raise forbidden(_WORKER_TOKEN_NOT_CONFIGURED)
        structlog.get_logger("api").warning(
            "worker_update_token_validation_skipped",
            environment=container.settings.environment,
        )
        return
    provided = worker_token.strip() if worker_token else ""
    if not compare_digest(expected_token, provided):
        raise forbidden("invalid worker update token")
