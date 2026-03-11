"""Job-domain routes for the canonical file API."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Request

from nova_file_api.activity import ActivityStore
from nova_file_api.dependencies import (
    ActivityStoreDep,
    AuthenticatorDep,
    IdempotencyStoreDep,
    JobServiceDep,
    MetricsDep,
    PrincipalDep,
    SettingsDep,
    authenticate_principal,
)
from nova_file_api.errors import forbidden, idempotency_conflict
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    EnqueueJobRequest,
    EnqueueJobResponse,
    JobCancelResponse,
    JobEvent,
    JobEventsResponse,
    JobListResponse,
    JobResultUpdateRequest,
    JobResultUpdateResponse,
    JobStatusResponse,
    Principal,
)
from nova_file_api.operation_ids import (
    CANCEL_JOB_OPERATION_ID,
    CREATE_JOB_OPERATION_ID,
    GET_JOB_STATUS_OPERATION_ID,
    LIST_JOB_EVENTS_OPERATION_ID,
    LIST_JOBS_OPERATION_ID,
    RETRY_JOB_OPERATION_ID,
    UPDATE_JOB_RESULT_OPERATION_ID,
)
from nova_file_api.routes.common import (
    IdempotencyKeyHeader,
    JobsLimitQuery,
    WorkerTokenHeader,
    emit_request_metric,
    validate_worker_update_token,
    validated_idempotency_key,
)

jobs_router = APIRouter(prefix="/v1", tags=["jobs"])


@jobs_router.post(
    "/jobs",
    operation_id=CREATE_JOB_OPERATION_ID,
    response_model=EnqueueJobResponse,
)
async def create_job(
    request: Request,
    payload: EnqueueJobRequest,
    settings: SettingsDep,
    metrics: MetricsDep,
    job_service: JobServiceDep,
    activity_store: ActivityStoreDep,
    idempotency_store: IdempotencyStoreDep,
    authenticator: AuthenticatorDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> EnqueueJobResponse:
    """Enqueue async processing job and return job id."""
    principal = await authenticate_principal(
        request=request,
        authenticator=authenticator,
        session_id=payload.session_id,
    )

    if not settings.jobs_enabled:
        raise forbidden("jobs API is disabled")

    key = validated_idempotency_key(
        settings=settings,
        idempotency_key=idempotency_key,
    )
    return await _enqueue_job_core(
        metrics=metrics,
        job_service=job_service,
        activity_store=activity_store,
        idempotency_store=idempotency_store,
        payload=payload,
        principal=principal,
        idempotency_key=key,
    )


@jobs_router.get(
    "/jobs/{job_id}",
    operation_id=GET_JOB_STATUS_OPERATION_ID,
    response_model=JobStatusResponse,
)
async def get_job_status(
    job_id: str,
    metrics: MetricsDep,
    job_service: JobServiceDep,
    activity_store: ActivityStoreDep,
    principal: PrincipalDep,
) -> JobStatusResponse:
    """Return status for the caller-owned job."""
    try:
        job = await job_service.get(
            job_id=job_id,
            scope_id=principal.scope_id,
        )
    except Exception as exc:
        await _record_job_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="jobs_status_failure_total",
            route_metric="jobs_status",
            log_event="jobs_status_request_failed",
            route_path="/v1/jobs/{job_id}",
            activity_event_type="jobs_status_failure",
            exc=exc,
            extra={"job_id": job_id},
        )
        raise

    metrics.incr("jobs_status_total")
    emit_request_metric(metrics=metrics, route="jobs_status", status="ok")
    return JobStatusResponse(job=job)


@jobs_router.post(
    "/jobs/{job_id}/cancel",
    operation_id=CANCEL_JOB_OPERATION_ID,
    response_model=JobCancelResponse,
)
async def cancel_job(
    job_id: str,
    metrics: MetricsDep,
    job_service: JobServiceDep,
    activity_store: ActivityStoreDep,
    principal: PrincipalDep,
) -> JobCancelResponse:
    """Cancel a caller-owned non-terminal job."""
    try:
        job = await job_service.cancel(
            job_id=job_id,
            scope_id=principal.scope_id,
        )
    except Exception as exc:
        await _record_job_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="jobs_cancel_failure_total",
            route_metric="jobs_cancel",
            log_event="jobs_cancel_request_failed",
            route_path="/v1/jobs/{job_id}/cancel",
            activity_event_type="jobs_cancel_failure",
            exc=exc,
            extra={"job_id": job_id},
        )
        raise

    try:
        await activity_store.record(
            principal=principal,
            event_type="jobs_cancel_success",
            details=f"job_id={job.job_id} status={job.status}",
        )
    except Exception:
        structlog.get_logger("api").exception(
            "jobs_cancel_activity_record_failed",
            job_id=job.job_id,
            status=job.status,
        )
    metrics.incr("jobs_cancel_total")
    emit_request_metric(metrics=metrics, route="jobs_cancel", status="ok")
    return JobCancelResponse(job_id=job.job_id, status=job.status)


@jobs_router.post(
    "/internal/jobs/{job_id}/result",
    operation_id=UPDATE_JOB_RESULT_OPERATION_ID,
    response_model=JobResultUpdateResponse,
)
async def update_job_result(
    job_id: str,
    payload: JobResultUpdateRequest,
    settings: SettingsDep,
    metrics: MetricsDep,
    job_service: JobServiceDep,
    activity_store: ActivityStoreDep,
    worker_token: WorkerTokenHeader = None,
) -> JobResultUpdateResponse:
    """Update job status/result from trusted worker-side processing."""
    if not settings.jobs_enabled:
        raise forbidden("jobs API is disabled")

    validate_worker_update_token(
        settings=settings,
        worker_token=worker_token,
    )
    worker_principal = Principal(
        subject="system:jobs-worker",
        scope_id="system:jobs-worker",
    )

    try:
        job = await job_service.update_result(
            job_id=job_id,
            status=payload.status,
            result=payload.result,
            error=payload.error,
        )
    except Exception as exc:
        await _record_job_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=worker_principal,
            metric_name="jobs_result_update_failure_total",
            route_metric="jobs_result_update",
            log_event="jobs_result_update_request_failed",
            route_path="/v1/internal/jobs/{job_id}/result",
            activity_event_type="jobs_result_update_failure",
            exc=exc,
            activity_details=(
                "worker result update failed "
                f"for job_id={job_id} status={payload.status}"
            ),
            extra={"job_id": job_id},
        )
        raise

    try:
        await activity_store.record(
            principal=worker_principal,
            event_type="jobs_result_update",
            details=(
                "worker result update accepted "
                f"for job_id={job_id} status={job.status}"
            ),
        )
    except Exception:
        structlog.get_logger("api").exception(
            "jobs_result_update_activity_record_failed",
            job_id=job_id,
            status=job.status,
        )
    metrics.incr("jobs_result_update_total")
    emit_request_metric(
        metrics=metrics,
        route="jobs_result_update",
        status="ok",
    )
    return JobResultUpdateResponse(
        job_id=job.job_id,
        status=job.status,
        updated_at=job.updated_at,
    )


@jobs_router.get(
    "/jobs",
    operation_id=LIST_JOBS_OPERATION_ID,
    response_model=JobListResponse,
)
async def list_jobs(
    job_service: JobServiceDep,
    principal: PrincipalDep,
    limit: JobsLimitQuery = 50,
) -> JobListResponse:
    """List caller-owned jobs with most recent first."""
    jobs = await job_service.list_for_scope(
        scope_id=principal.scope_id,
        limit=limit,
    )
    return JobListResponse(jobs=jobs)


@jobs_router.post(
    "/jobs/{job_id}/retry",
    operation_id=RETRY_JOB_OPERATION_ID,
    response_model=EnqueueJobResponse,
)
async def retry_job(
    job_id: str,
    settings: SettingsDep,
    metrics: MetricsDep,
    job_service: JobServiceDep,
    activity_store: ActivityStoreDep,
    principal: PrincipalDep,
) -> EnqueueJobResponse:
    """Retry a terminal failed or canceled job."""
    if not settings.jobs_enabled:
        raise forbidden("jobs API is disabled")
    try:
        retried = await job_service.retry(
            job_id=job_id,
            scope_id=principal.scope_id,
        )
    except Exception as exc:
        await _record_job_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="jobs_retry_failure_total",
            route_metric="jobs_retry",
            log_event="jobs_retry_request_failed",
            route_path="/v1/jobs/{job_id}/retry",
            activity_event_type="jobs_retry_failure",
            exc=exc,
            extra={"job_id": job_id},
        )
        raise
    return EnqueueJobResponse(job_id=retried.job_id, status=retried.status)


@jobs_router.get(
    "/jobs/{job_id}/events",
    operation_id=LIST_JOB_EVENTS_OPERATION_ID,
    response_model=JobEventsResponse,
)
async def list_job_events(
    job_id: str,
    job_service: JobServiceDep,
    principal: PrincipalDep,
) -> JobEventsResponse:
    """Return poll events with an SSE-compatible envelope."""
    job = await job_service.get(
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


async def _enqueue_job_core(
    *,
    metrics: MetricsCollector,
    job_service: Any,
    activity_store: ActivityStore,
    idempotency_store: IdempotencyStore,
    payload: EnqueueJobRequest,
    principal: Principal,
    idempotency_key: str | None,
) -> EnqueueJobResponse:
    """Execute the enqueue and idempotency workflow."""
    request_payload = payload.model_dump(mode="json")
    claimed_idempotency = False

    if idempotency_key is not None:
        replay = await idempotency_store.load_response(
            route="/v1/jobs",
            scope_id=principal.scope_id,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )
        if replay is not None:
            metrics.incr("idempotency_replays_total")
            return EnqueueJobResponse.model_validate(replay)

        claimed_idempotency = await idempotency_store.claim_request(
            route="/v1/jobs",
            scope_id=principal.scope_id,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )
        if not claimed_idempotency:
            replay = await idempotency_store.load_response(
                route="/v1/jobs",
                scope_id=principal.scope_id,
                idempotency_key=idempotency_key,
                request_payload=request_payload,
            )
            if replay is not None:
                metrics.incr("idempotency_replays_total")
                return EnqueueJobResponse.model_validate(replay)
            raise idempotency_conflict(
                "idempotency request is already in progress"
            )

    try:
        with metrics.timed("jobs_enqueue_ms"):
            job = await job_service.enqueue(
                job_type=payload.job_type,
                payload=payload.payload,
                scope_id=principal.scope_id,
            )
    except Exception as exc:
        await _record_job_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="jobs_enqueue_failure_total",
            route_metric="jobs_enqueue",
            log_event="jobs_enqueue_request_failed",
            route_path="/v1/jobs",
            activity_event_type="jobs_enqueue_failure",
            exc=exc,
            extra={"idempotency_key": idempotency_key},
        )
        if idempotency_key is not None and claimed_idempotency:
            await idempotency_store.discard_claim(
                route="/v1/jobs",
                scope_id=principal.scope_id,
                idempotency_key=idempotency_key,
            )
        raise

    response = EnqueueJobResponse(job_id=job.job_id, status=job.status)
    try:
        await activity_store.record(
            principal=principal,
            event_type="jobs_enqueue",
        )
        metrics.incr("jobs_enqueue_total")
        emit_request_metric(
            metrics=metrics,
            route="jobs_enqueue",
            status="ok",
        )
        if idempotency_key is not None:
            await idempotency_store.store_response(
                route="/v1/jobs",
                scope_id=principal.scope_id,
                idempotency_key=idempotency_key,
                request_payload=request_payload,
                response_payload=response.model_dump(mode="json"),
            )
    except Exception as exc:
        await _record_job_failure(
            metrics=metrics,
            activity_store=activity_store,
            principal=principal,
            metric_name="jobs_enqueue_failure_total",
            route_metric="jobs_enqueue",
            log_event="jobs_enqueue_response_finalize_failed",
            route_path="/v1/jobs",
            activity_event_type="jobs_enqueue_failure",
            exc=exc,
            extra={"idempotency_key": idempotency_key},
        )
        if idempotency_key is not None and claimed_idempotency:
            await idempotency_store.discard_claim(
                route="/v1/jobs",
                scope_id=principal.scope_id,
                idempotency_key=idempotency_key,
            )
        raise
    return response


async def _record_job_failure(
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
    """Record canonical metrics, logs, and activity for job failures."""
    metrics.incr(metric_name)
    emit_request_metric(metrics=metrics, route=route_metric, status="error")
    log_fields: dict[str, object] = {
        "route": route_path,
        "scope_id": principal.scope_id,
        "error": type(exc).__name__,
        "error_detail": str(exc),
    }
    if extra:
        log_fields.update(extra)
    structlog.get_logger("api").exception(log_event, **log_fields)
    try:
        await activity_store.record(
            principal=principal,
            event_type=activity_event_type,
            details=activity_details or str(exc),
        )
    except Exception:
        structlog.get_logger("api").exception(
            "jobs_failure_activity_record_failed",
            route=route_path,
            scope_id=principal.scope_id,
            event_type=activity_event_type,
        )
