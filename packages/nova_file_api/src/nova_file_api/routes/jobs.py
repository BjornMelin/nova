"""Job-domain routes for the canonical file API."""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from nova_file_api.activity import ActivityStore
from nova_file_api.dependencies import (
    ActivityStoreDep,
    IdempotencyStoreDep,
    JobServiceDep,
    MetricsDep,
    PrincipalDep,
    SettingsDep,
)
from nova_file_api.errors import forbidden
from nova_file_api.guarded_mutation import run_guarded_mutation
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.jobs import JobService
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    EnqueueJobRequest,
    EnqueueJobResponse,
    JobCancelResponse,
    JobEvent,
    JobEventsResponse,
    JobListResponse,
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
)
from nova_file_api.routes.common import (
    AUTH_ERROR_RESPONSES,
    IDEMPOTENCY_CONFLICT_RESPONSE,
    JOB_MUTATION_UNAVAILABLE_RESPONSE,
    IdempotencyKeyHeader,
    JobsLimitQuery,
    emit_request_metric,
    merge_openapi_responses,
    validated_idempotency_key,
)

jobs_router = APIRouter(
    prefix="/v1",
    tags=["jobs"],
    responses=merge_openapi_responses(AUTH_ERROR_RESPONSES),
)


@jobs_router.post(
    "/jobs",
    operation_id=CREATE_JOB_OPERATION_ID,
    response_model=EnqueueJobResponse,
    responses=merge_openapi_responses(
        IDEMPOTENCY_CONFLICT_RESPONSE,
        JOB_MUTATION_UNAVAILABLE_RESPONSE,
    ),
)
async def create_job(
    payload: EnqueueJobRequest,
    settings: SettingsDep,
    metrics: MetricsDep,
    job_service: JobServiceDep,
    activity_store: ActivityStoreDep,
    idempotency_store: IdempotencyStoreDep,
    principal: PrincipalDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> EnqueueJobResponse:
    """Enqueue async processing job and return job id."""
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

    try:
        metrics.incr("jobs_status_total")
        emit_request_metric(metrics=metrics, route="jobs_status", status="ok")
    except Exception:
        structlog.get_logger("api").exception(
            "jobs_status_success_side_effects_failed",
            route="/v1/jobs/{job_id}",
            scope_id=principal.scope_id,
            job_id=job_id,
        )
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
    try:
        metrics.incr("jobs_cancel_total")
        emit_request_metric(metrics=metrics, route="jobs_cancel", status="ok")
    except Exception:
        structlog.get_logger("api").exception(
            "jobs_cancel_success_side_effects_failed",
            route="/v1/jobs/{job_id}/cancel",
            scope_id=principal.scope_id,
            job_id=job_id,
        )
    return JobCancelResponse(job_id=job.job_id, status=job.status)


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
    job_service: JobService,
    activity_store: ActivityStore,
    idempotency_store: IdempotencyStore,
    payload: EnqueueJobRequest,
    principal: Principal,
    idempotency_key: str | None,
) -> EnqueueJobResponse:
    """Execute the enqueue and idempotency workflow."""
    request_payload = payload.model_dump(mode="json")

    async def _execute() -> EnqueueJobResponse:
        with metrics.timed("jobs_enqueue_ms"):
            job = await job_service.enqueue(
                job_type=payload.job_type,
                payload=payload.payload,
                scope_id=principal.scope_id,
            )
        return EnqueueJobResponse(job_id=job.job_id, status=job.status)

    async def _on_failure(exc: Exception) -> None:
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

    async def _on_success(response: EnqueueJobResponse) -> None:
        del response
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
        except Exception:
            structlog.get_logger("api").exception(
                "jobs_enqueue_response_finalize_failed",
                route="/v1/jobs",
                scope_id=principal.scope_id,
                idempotency_key=idempotency_key,
            )

    def _replay_metric() -> None:
        metrics.incr("idempotency_replays_total")

    return await run_guarded_mutation(
        route="/v1/jobs",
        scope_id=principal.scope_id,
        request_payload=request_payload,
        idempotency_store=idempotency_store,
        idempotency_key=idempotency_key,
        response_model=EnqueueJobResponse,
        replay_metric=_replay_metric,
        execute=_execute,
        on_failure=_on_failure,
        on_success=_on_success,
        store_response_failure_event=(
            "jobs_enqueue_idempotency_store_response_failed"
        ),
        store_response_failure_extra={
            "route": "/v1/jobs",
            "scope_id": principal.scope_id,
            "idempotency_key": idempotency_key,
        },
        store_response_failure_mode="raise",
    )


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
