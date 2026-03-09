"""Job-domain routes for the canonical file API."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Header, Query

from nova_file_api.dependencies import RequestContext, RequestContextDep
from nova_file_api.errors import forbidden
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
from nova_file_api.routes.common import (
    emit_request_metric,
    validate_worker_update_token,
    validated_idempotency_key,
)
from nova_file_api.routes.idempotent_mutation import run_idempotent_mutation

jobs_router = APIRouter(prefix="/v1", tags=["jobs"])


@jobs_router.post(
    "/jobs",
    response_model=EnqueueJobResponse,
)
async def create_job(
    payload: EnqueueJobRequest,
    context: RequestContextDep,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
) -> EnqueueJobResponse:
    """Enqueue async processing job and return job id."""
    container = context.container
    principal = await context.authenticate(session_id=payload.session_id)

    if not container.settings.jobs_enabled:
        raise forbidden("jobs API is disabled")

    key = validated_idempotency_key(
        container=container,
        idempotency_key=idempotency_key,
    )
    return await _enqueue_job_core(
        context=context,
        payload=payload,
        principal=principal,
        idempotency_key=key,
    )


@jobs_router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
)
async def get_job_status(
    job_id: str,
    context: RequestContextDep,
) -> JobStatusResponse:
    """Return status for the caller-owned job."""
    container = context.container
    principal = await context.authenticate(session_id=None)
    try:
        job = await context.run_blocking(
            container.job_service.get,
            job_id=job_id,
            scope_id=principal.scope_id,
        )
    except Exception as exc:
        await _record_job_failure(
            context=context,
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

    container.metrics.incr("jobs_status_total")
    emit_request_metric(container=container, route="jobs_status", status="ok")
    return JobStatusResponse(job=job)


@jobs_router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobCancelResponse,
)
async def cancel_job(
    job_id: str,
    context: RequestContextDep,
) -> JobCancelResponse:
    """Cancel a caller-owned non-terminal job."""
    container = context.container
    principal = await context.authenticate(session_id=None)

    try:
        job = await context.run_blocking(
            container.job_service.cancel,
            job_id=job_id,
            scope_id=principal.scope_id,
        )
    except Exception as exc:
        await _record_job_failure(
            context=context,
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

    await context.run_blocking(
        container.activity_store.record,
        principal=principal,
        event_type="jobs_cancel_success",
        details=f"job_id={job.job_id} status={job.status}",
    )
    container.metrics.incr("jobs_cancel_total")
    emit_request_metric(container=container, route="jobs_cancel", status="ok")
    return JobCancelResponse(job_id=job.job_id, status=job.status)


@jobs_router.post(
    "/internal/jobs/{job_id}/result",
    response_model=JobResultUpdateResponse,
)
async def update_job_result(
    job_id: str,
    payload: JobResultUpdateRequest,
    context: RequestContextDep,
    worker_token: str | None = Header(default=None, alias="X-Worker-Token"),
) -> JobResultUpdateResponse:
    """Update job status/result from trusted worker-side processing."""
    container = context.container
    if not container.settings.jobs_enabled:
        raise forbidden("jobs API is disabled")

    validate_worker_update_token(
        container=container,
        worker_token=worker_token,
    )
    worker_principal = Principal(
        subject="system:jobs-worker",
        scope_id="system:jobs-worker",
    )

    try:
        job = await context.run_blocking(
            container.job_service.update_result,
            job_id=job_id,
            status=payload.status,
            result=payload.result,
            error=payload.error,
        )
    except Exception as exc:
        await _record_job_failure(
            context=context,
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

    await context.run_blocking(
        container.activity_store.record,
        principal=worker_principal,
        event_type="jobs_result_update",
        details=(
            "worker result update accepted "
            f"for job_id={job_id} status={job.status}"
        ),
    )
    container.metrics.incr("jobs_result_update_total")
    emit_request_metric(
        container=container,
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
    response_model=JobListResponse,
)
async def list_jobs(
    context: RequestContextDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> JobListResponse:
    """List caller-owned jobs with most recent first."""
    principal = await context.authenticate(session_id=None)
    jobs = await context.run_blocking(
        context.container.job_service.list_for_scope,
        scope_id=principal.scope_id,
        limit=limit,
    )
    return JobListResponse(jobs=jobs)


@jobs_router.post(
    "/jobs/{job_id}/retry",
    response_model=EnqueueJobResponse,
)
async def retry_job(
    job_id: str,
    context: RequestContextDep,
) -> EnqueueJobResponse:
    """Retry a terminal failed or canceled job."""
    container = context.container
    principal = await context.authenticate(session_id=None)
    if not container.settings.jobs_enabled:
        raise forbidden("jobs API is disabled")
    retried = await context.run_blocking(
        container.job_service.retry,
        job_id=job_id,
        scope_id=principal.scope_id,
    )
    return EnqueueJobResponse(job_id=retried.job_id, status=retried.status)


@jobs_router.get(
    "/jobs/{job_id}/events",
    response_model=JobEventsResponse,
)
async def list_job_events(
    job_id: str,
    context: RequestContextDep,
) -> JobEventsResponse:
    """Return poll events with an SSE-compatible envelope."""
    principal = await context.authenticate(session_id=None)
    job = await context.run_blocking(
        context.container.job_service.get,
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
    context: RequestContext,
    payload: EnqueueJobRequest,
    principal: Principal,
    idempotency_key: str | None,
) -> EnqueueJobResponse:
    """Execute the enqueue and idempotency workflow."""
    container = context.container
    request_payload = payload.model_dump(mode="json")

    try:

        async def execute() -> EnqueueJobResponse:
            with container.metrics.timed("jobs_enqueue_ms"):
                job = await context.run_blocking(
                    container.job_service.enqueue,
                    job_type=payload.job_type,
                    payload=payload.payload,
                    scope_id=principal.scope_id,
                )
            return EnqueueJobResponse(job_id=job.job_id, status=job.status)

        response = await run_idempotent_mutation(
            container=container,
            route="/v1/jobs",
            scope_id=principal.scope_id,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            response_model=EnqueueJobResponse,
            execute=execute,
        )
    except Exception as exc:
        await _record_job_failure(
            context=context,
            principal=principal,
            metric_name="jobs_enqueue_failure_total",
            route_metric="jobs_enqueue",
            log_event="jobs_enqueue_request_failed",
            route_path="/v1/jobs",
            activity_event_type="jobs_enqueue_failure",
            exc=exc,
            extra={"idempotency_key": idempotency_key},
        )
        raise
    await context.run_blocking(
        container.activity_store.record,
        principal=principal,
        event_type="jobs_enqueue",
    )
    container.metrics.incr("jobs_enqueue_total")
    emit_request_metric(container=container, route="jobs_enqueue", status="ok")
    return response


async def _record_job_failure(
    *,
    context: RequestContext,
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
    container = context.container
    container.metrics.incr(metric_name)
    emit_request_metric(container=container, route=route_metric, status="error")
    log_fields: dict[str, object] = {
        "route": route_path,
        "scope_id": principal.scope_id,
        "error": type(exc).__name__,
        "error_detail": str(exc),
    }
    if extra:
        log_fields.update(extra)
    structlog.get_logger("api").exception(log_event, **log_fields)
    await context.run_blocking(
        container.activity_store.record,
        principal=principal,
        event_type=activity_event_type,
        details=activity_details or str(exc),
    )
