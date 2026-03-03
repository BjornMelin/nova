"""FastAPI routers for canonical v1 API and operational endpoints."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from hmac import compare_digest
from typing import Any

import anyio
import structlog
from fastapi import APIRouter, Header, Query, Request

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
    CapabilitiesResponse,
    CapabilityDescriptor,
    CompleteUploadRequest,
    CompleteUploadResponse,
    EnqueueJobRequest,
    EnqueueJobResponse,
    HealthResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    JobCancelResponse,
    JobEvent,
    JobEventsResponse,
    JobListResponse,
    JobResultUpdateRequest,
    JobResultUpdateResponse,
    JobStatusResponse,
    MetricsSummaryResponse,
    PresignDownloadRequest,
    PresignDownloadResponse,
    Principal,
    ReadinessResponse,
    ReleaseInfoResponse,
    ResourcePlanItem,
    ResourcePlanRequest,
    ResourcePlanResponse,
    SignPartsRequest,
    SignPartsResponse,
)

transfer_router = APIRouter(prefix="/v1/transfers", tags=["transfers"])
ops_router = APIRouter(tags=["ops"])
v1_router = APIRouter(prefix="/v1", tags=["v1"])
_WORKER_TOKEN_NOT_CONFIGURED = "worker update token not configured"  # noqa: S105
_API_THREAD_LIMITER_STATE_KEY = "api_thread_limiter"


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
            route="/v1/transfers/uploads/initiate",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
        )
        if replay is not None:
            container.metrics.incr("idempotency_replays_total")
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
                container.metrics.incr("idempotency_replays_total")
                return InitiateUploadResponse.model_validate(replay)
            raise idempotency_conflict(
                "idempotency request is already in progress"
            )

    try:
        with container.metrics.timed("uploads_initiate_ms"):
            response = await _run_blocking(
                request,
                container.transfer_service.initiate_upload,
                payload,
                principal,
            )
    except Exception as exc:
        container.metrics.incr("uploads_initiate_failure_total")
        _emit_request_metric(
            container=container, route="uploads_initiate", status="error"
        )
        log = structlog.get_logger("api")
        log.exception(
            "initiate_upload_request_failed",
            route="/v1/transfers/uploads/initiate",
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await _run_blocking(
            request,
            container.activity_store.record,
            principal=principal,
            event_type="uploads_initiate_failure",
            details=str(exc),
        )
        if key is not None and claimed_idempotency:
            await container.idempotency_store.discard_claim(
                route="/v1/transfers/uploads/initiate",
                scope_id=principal.scope_id,
                idempotency_key=key,
            )
        raise

    if key is not None:
        await container.idempotency_store.store_response(
            route="/v1/transfers/uploads/initiate",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
            response_payload=response.model_dump(mode="json"),
        )

    container.metrics.incr("uploads_initiate_total")
    await _run_blocking(
        request,
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
            response = await _run_blocking(
                request,
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
            route="/v1/transfers/uploads/sign-parts",
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await _run_blocking(
            request,
            container.activity_store.record,
            principal=principal,
            event_type="uploads_sign_parts_failure",
            details=str(exc),
        )
        raise

    container.metrics.incr("uploads_sign_parts_total")
    await _run_blocking(
        request,
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
            response = await _run_blocking(
                request,
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
            route="/v1/transfers/uploads/complete",
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await _run_blocking(
            request,
            container.activity_store.record,
            principal=principal,
            event_type="uploads_complete_failure",
            details=str(exc),
        )
        raise

    container.metrics.incr("uploads_complete_total")
    await _run_blocking(
        request,
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
            response = await _run_blocking(
                request,
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
            route="/v1/transfers/uploads/abort",
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await _run_blocking(
            request,
            container.activity_store.record,
            principal=principal,
            event_type="uploads_abort_failure",
            details=str(exc),
        )
        raise

    container.metrics.incr("uploads_abort_total")
    await _run_blocking(
        request,
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
            response = await _run_blocking(
                request,
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
            route="/v1/transfers/downloads/presign",
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await _run_blocking(
            request,
            container.activity_store.record,
            principal=principal,
            event_type="downloads_presign_failure",
            details=str(exc),
        )
        raise

    container.metrics.incr("downloads_presign_total")
    await _run_blocking(
        request,
        container.activity_store.record,
        principal=principal,
        event_type="downloads_presign",
    )
    _emit_request_metric(
        container=container, route="downloads_presign", status="ok"
    )
    return response


@v1_router.post("/jobs", response_model=EnqueueJobResponse)
async def create_job(
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
    return await _enqueue_job_core(
        container=container,
        request=request,
        payload=payload,
        principal=principal,
        idempotency_key=key,
    )


async def _enqueue_job_core(
    *,
    container: AppContainer,
    request: Request,
    payload: EnqueueJobRequest,
    principal: Principal,
    idempotency_key: str | None,
) -> EnqueueJobResponse:
    """Execute enqueue/idempotency workflow for authenticated callers."""
    key = idempotency_key
    request_payload = payload.model_dump(mode="json")
    claimed_idempotency = False
    if key is not None:
        replay = await container.idempotency_store.load_response(
            route="/v1/jobs",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
        )
        if replay is not None:
            container.metrics.incr("idempotency_replays_total")
            return EnqueueJobResponse.model_validate(replay)
        claimed_idempotency = await container.idempotency_store.claim_request(
            route="/v1/jobs",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
        )
        if not claimed_idempotency:
            replay = await container.idempotency_store.load_response(
                route="/v1/jobs",
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
            job = await _run_blocking(
                request,
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
            route="/v1/jobs",
            scope_id=principal.scope_id,
            idempotency_key=key,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await _run_blocking(
            request,
            container.activity_store.record,
            principal=principal,
            event_type="jobs_enqueue_failure",
            details=str(exc),
        )
        if key is not None and claimed_idempotency:
            await container.idempotency_store.discard_claim(
                route="/v1/jobs",
                scope_id=principal.scope_id,
                idempotency_key=key,
            )
        raise

    response = EnqueueJobResponse(job_id=job.job_id, status=job.status)
    if key is not None:
        await container.idempotency_store.store_response(
            route="/v1/jobs",
            scope_id=principal.scope_id,
            idempotency_key=key,
            request_payload=request_payload,
            response_payload=response.model_dump(mode="json"),
        )
    await _run_blocking(
        request,
        container.activity_store.record,
        principal=principal,
        event_type="jobs_enqueue",
    )
    container.metrics.incr("jobs_enqueue_total")
    _emit_request_metric(container=container, route="jobs_enqueue", status="ok")
    return response


@v1_router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, request: Request) -> JobStatusResponse:
    """Return status for caller-owned job."""
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request,
        session_id=None,
    )
    try:
        job = await _run_blocking(
            request,
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
            route="/v1/jobs/{job_id}",
            job_id=job_id,
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await _run_blocking(
            request,
            container.activity_store.record,
            principal=principal,
            event_type="jobs_status_failure",
            details=str(exc),
        )
        raise
    container.metrics.incr("jobs_status_total")
    _emit_request_metric(container=container, route="jobs_status", status="ok")
    return JobStatusResponse(job=job)


@v1_router.post("/jobs/{job_id}/cancel", response_model=JobCancelResponse)
async def cancel_job(job_id: str, request: Request) -> JobCancelResponse:
    """Cancel caller-owned non-terminal job."""
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request,
        session_id=None,
    )
    try:
        job = await _run_blocking(
            request,
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
            route="/v1/jobs/{job_id}/cancel",
            job_id=job_id,
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await _run_blocking(
            request,
            container.activity_store.record,
            principal=principal,
            event_type="jobs_cancel_failure",
            details=str(exc),
        )
        raise
    await _run_blocking(
        request,
        container.activity_store.record,
        principal=principal,
        event_type="jobs_cancel_success",
        details=f"job_id={job.job_id} status={job.status}",
    )
    container.metrics.incr("jobs_cancel_total")
    _emit_request_metric(container=container, route="jobs_cancel", status="ok")
    return JobCancelResponse(job_id=job.job_id, status=job.status)


@v1_router.post(
    "/internal/jobs/{job_id}/result",
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
    worker_principal = Principal(
        subject="system:jobs-worker",
        scope_id="system:jobs-worker",
    )
    try:
        job = await _run_blocking(
            request,
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
            route="/v1/internal/jobs/{job_id}/result",
            job_id=job_id,
            error=type(exc).__name__,
            error_detail=str(exc),
        )
        await _run_blocking(
            request,
            container.activity_store.record,
            principal=worker_principal,
            event_type="jobs_result_update_failure",
            details=(
                "worker result update failed "
                f"for job_id={job_id} status={payload.status}"
            ),
        )
        raise
    await _run_blocking(
        request,
        container.activity_store.record,
        principal=worker_principal,
        event_type="jobs_result_update",
        details=(
            "worker result update accepted "
            f"for job_id={job_id} status={job.status}"
        ),
    )
    container.metrics.incr("jobs_result_update_total")
    _emit_request_metric(
        container=container, route="jobs_result_update", status="ok"
    )
    return JobResultUpdateResponse(
        job_id=job.job_id,
        status=job.status,
        updated_at=job.updated_at,
    )


@v1_router.get("/jobs", response_model=JobListResponse)
async def v1_list_jobs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
) -> JobListResponse:
    """List caller-owned jobs with most recent first.

    Args:
        request: FastAPI request context.
        limit: Maximum number of jobs to return.

    Returns:
        JobListResponse: Caller-scoped jobs in newest-first order.

    Raises:
        HTTPException: If caller authentication fails.
    """
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request, session_id=None
    )
    jobs = await _run_blocking(
        request,
        container.job_service.list_for_scope,
        scope_id=principal.scope_id,
        limit=limit,
    )
    return JobListResponse(jobs=jobs)


@v1_router.post("/jobs/{job_id}/retry", response_model=EnqueueJobResponse)
async def v1_retry_job(job_id: str, request: Request) -> EnqueueJobResponse:
    """Retry a terminal failed/canceled job.

    Args:
        job_id: Target job identifier.
        request: FastAPI request context.

    Returns:
        EnqueueJobResponse: Newly queued retry job metadata.

    Raises:
        HTTPException: If jobs are disabled or caller/job constraints fail.
    """
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request, session_id=None
    )
    if not container.settings.jobs_enabled:
        raise forbidden("jobs API is disabled")
    retried = await _run_blocking(
        request,
        container.job_service.retry,
        job_id=job_id,
        scope_id=principal.scope_id,
    )
    return EnqueueJobResponse(job_id=retried.job_id, status=retried.status)


@v1_router.get("/jobs/{job_id}/events", response_model=JobEventsResponse)
async def v1_job_events(job_id: str, request: Request) -> JobEventsResponse:
    """Return poll events with an SSE-compatible envelope.

    Args:
        job_id: Target job identifier.
        request: FastAPI request context.

    Returns:
        JobEventsResponse: Synthetic event stream for polling consumers.

    Raises:
        HTTPException: If caller authentication fails or job is inaccessible.
    """
    container = get_container(request)
    principal = await container.authenticator.authenticate(
        request=request, session_id=None
    )
    job = await _run_blocking(
        request,
        container.job_service.get,
        job_id=job_id,
        scope_id=principal.scope_id,
    )
    event = JobEvent(
        event_id=f"{job.job_id}:{job.updated_at.isoformat()}",
        job_id=job.job_id,
        status=job.status,
        timestamp=job.updated_at,
        data={"result": job.result, "error": job.error},
    )
    return JobEventsResponse(
        job_id=job.job_id,
        events=[event],
        next_cursor=event.event_id,
    )


@v1_router.get("/capabilities", response_model=CapabilitiesResponse)
async def v1_capabilities(request: Request) -> CapabilitiesResponse:
    """Expose runtime capability matrix for conformance consumers.

    Args:
        request: FastAPI request context.

    Returns:
        CapabilitiesResponse: Runtime capability declarations.
    """
    container = get_container(request)
    capabilities = [
        CapabilityDescriptor(
            key="jobs", enabled=container.settings.jobs_enabled
        ),
        CapabilityDescriptor(
            key="jobs.events.poll",
            enabled=container.settings.jobs_enabled,
        ),
        CapabilityDescriptor(
            key="transfers",
            enabled=container.settings.file_transfer_enabled,
        ),
    ]
    return CapabilitiesResponse(capabilities=capabilities)


@v1_router.post("/resources/plan", response_model=ResourcePlanResponse)
async def v1_resources_plan(
    payload: ResourcePlanRequest,
    request: Request,
) -> ResourcePlanResponse:
    """Plan supportability for requested resource keys.

    Args:
        payload: Requested resource key list.
        request: FastAPI request context.

    Returns:
        ResourcePlanResponse: Supportability decisions per requested key.
    """
    container = get_container(request)
    available = {"jobs", "transfers", "downloads", "uploads"}
    plan = [
        ResourcePlanItem(
            resource=resource,
            supported=resource in available,
            reason=None if resource in available else "unsupported_resource",
        )
        for resource in payload.resources
    ]
    if container.settings.jobs_enabled is False:
        plan = [
            item.model_copy(
                update={"supported": False, "reason": "jobs_disabled"}
            )
            if item.resource == "jobs"
            else item
            for item in plan
        ]
    if container.settings.file_transfer_enabled is False:
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


@v1_router.get("/releases/info", response_model=ReleaseInfoResponse)
async def v1_releases_info(request: Request) -> ReleaseInfoResponse:
    """Return release metadata.

    Args:
        request: FastAPI request context.

    Returns:
        ReleaseInfoResponse: Service name, version, and environment data.
    """
    container = get_container(request)
    return ReleaseInfoResponse(
        name=container.settings.app_name,
        version=container.settings.app_version,
        environment=container.settings.environment,
    )


@v1_router.get("/health/live", response_model=HealthResponse)
async def v1_health_live() -> HealthResponse:
    """Return v1 liveness status.

    Returns:
        HealthResponse: Liveness success payload.
    """
    return HealthResponse(ok=True)


@v1_router.get("/health/ready", response_model=ReadinessResponse)
async def v1_health_ready(request: Request) -> ReadinessResponse:
    """Return v1 readiness status.

    Args:
        request: FastAPI request context.

    Returns:
        ReadinessResponse: Dependency readiness checks.
    """
    return await readyz(request=request)


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
        activity=await _run_blocking(
            request,
            container.activity_store.summary,
        ),
    )


async def readyz(request: Request) -> ReadinessResponse:
    """Return readiness checks for critical dependencies."""
    container = get_container(request)
    logger = structlog.get_logger("api")
    try:
        shared_cache = await container.shared_cache.ping()
    except Exception:
        logger.exception(
            "readyz_shared_cache_ping_failed",
            route="/v1/health/ready",
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


async def _run_blocking[**P, R](
    request: Request,
    fn: Callable[P, R],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    limiter = _api_thread_limiter(request)
    return await anyio.to_thread.run_sync(
        partial(fn, *args, **kwargs),
        limiter=limiter,
    )


def _api_thread_limiter(request: Request) -> Any:
    limiter = getattr(request.app.state, _API_THREAD_LIMITER_STATE_KEY, None)
    if limiter is None:
        return anyio.to_thread.current_default_thread_limiter()
    return limiter


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
    expected_token = expected_token.strip()
    provided = worker_token.strip() if worker_token else ""
    if not compare_digest(expected_token, provided):
        raise forbidden("invalid worker update token")
