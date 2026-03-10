"""Job-domain routes for the canonical file API."""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from nova_file_api.dependencies import RequestContext, RequestContextDep
from nova_file_api.errors import forbidden, idempotency_conflict
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
    payload: EnqueueJobRequest,
    context: RequestContextDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> EnqueueJobResponse:
    """
    Enqueue a job for processing.
    
    Parameters:
        idempotency_key (IdempotencyKeyHeader | None): Optional idempotency key from the `Idempotency-Key` header used to deduplicate or replay requests.
    
    Returns:
        EnqueueJobResponse: Object containing the created `job_id` and the job's initial `status`.
    """
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
    operation_id=GET_JOB_STATUS_OPERATION_ID,
    response_model=JobStatusResponse,
)
async def get_job_status(
    job_id: str,
    context: RequestContextDep,
) -> JobStatusResponse:
    """
    Retrieve the status and details of a job owned by the caller.
    
    Returns:
        JobStatusResponse: The job's details and current status.
    """
    container = context.container
    principal = await context.authenticate(session_id=None)
    try:
        job = await container.job_service.get(
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
    operation_id=CANCEL_JOB_OPERATION_ID,
    response_model=JobCancelResponse,
)
async def cancel_job(
    job_id: str,
    context: RequestContextDep,
) -> JobCancelResponse:
    """
    Cancel a non-terminal job owned by the caller.
    
    Returns:
        JobCancelResponse: The cancelled job's `job_id` and current `status`.
    """
    container = context.container
    principal = await context.authenticate(session_id=None)

    try:
        job = await container.job_service.cancel(
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

    try:
        await container.activity_store.record(
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
    container.metrics.incr("jobs_cancel_total")
    emit_request_metric(container=container, route="jobs_cancel", status="ok")
    return JobCancelResponse(job_id=job.job_id, status=job.status)


@jobs_router.post(
    "/internal/jobs/{job_id}/result",
    operation_id=UPDATE_JOB_RESULT_OPERATION_ID,
    response_model=JobResultUpdateResponse,
)
async def update_job_result(
    job_id: str,
    payload: JobResultUpdateRequest,
    context: RequestContextDep,
    worker_token: WorkerTokenHeader = None,
) -> JobResultUpdateResponse:
    """
    Accept and apply a job status and result update submitted by an authorized worker.
    
    Validates the worker token, updates the job's status/result, records an activity event and metrics, and returns the job's updated state.
    
    Parameters:
        payload (JobResultUpdateRequest): Contains the new `status`, optional `result`, and optional `error` details to apply to the job.
        worker_token (WorkerTokenHeader | None): Worker authentication token supplied by the caller (from the X-Worker-Token header).
    
    Returns:
        JobResultUpdateResponse: The updated job information containing `job_id`, `status`, and `updated_at`.
    """
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
        job = await container.job_service.update_result(
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

    try:
        await container.activity_store.record(
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
    operation_id=LIST_JOBS_OPERATION_ID,
    response_model=JobListResponse,
)
async def list_jobs(
    context: RequestContextDep,
    limit: JobsLimitQuery = 50,
) -> JobListResponse:
    """
    List the caller's jobs ordered most recent first.
    
    Parameters:
        limit (JobsLimitQuery): Maximum number of jobs to return (validated and bounded by JobsLimitQuery).
    
    Returns:
        JobListResponse: Response object containing the jobs ordered by recency (newest first).
    """
    principal = await context.authenticate(session_id=None)
    jobs = await context.container.job_service.list_for_scope(
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
    context: RequestContextDep,
) -> EnqueueJobResponse:
    """
    Retry a terminal failed or canceled job owned by the caller.
    
    Parameters:
        job_id (str): Identifier of the job to retry.
    
    Returns:
        EnqueueJobResponse: The retried job's `job_id` and current `status`.
    
    Raises:
        HTTPException: If the jobs API is disabled (forbidden).
    """
    container = context.container
    principal = await context.authenticate(session_id=None)
    if not container.settings.jobs_enabled:
        raise forbidden("jobs API is disabled")
    try:
        retried = await container.job_service.retry(
            job_id=job_id,
            scope_id=principal.scope_id,
        )
    except Exception as exc:
        await _record_job_failure(
            context=context,
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
    context: RequestContextDep,
) -> JobEventsResponse:
    """
    Return the latest poll events for a job in an SSE-compatible envelope.
    
    Returns:
        JobEventsResponse: An envelope containing the job_id, a single JobEvent reflecting the job's current status, result, and error, and next_cursor set to that event's id.
    """
    principal = await context.authenticate(session_id=None)
    job = await context.container.job_service.get(
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
    """
    Enqueue a job for processing and apply idempotency handling for the caller's scope.
    
    If an idempotency key is provided, the function will attempt to replay a stored response, claim the key for an in-flight request, and store the resulting response for future replays. On success this records an activity and increments enqueue metrics; on failure it records a job failure and cleans up any idempotency claim.
    
    Parameters:
        idempotency_key (str | None): Optional idempotency key used to detect or claim duplicate enqueue requests within the principal's scope.
    
    Returns:
        EnqueueJobResponse: The enqueued job's identifier and current status.
    """
    container = context.container
    request_payload = payload.model_dump(mode="json")
    claimed_idempotency = False

    if idempotency_key is not None:
        replay = await container.idempotency_store.load_response(
            route="/v1/jobs",
            scope_id=principal.scope_id,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )
        if replay is not None:
            container.metrics.incr("idempotency_replays_total")
            return EnqueueJobResponse.model_validate(replay)

        claimed_idempotency = await container.idempotency_store.claim_request(
            route="/v1/jobs",
            scope_id=principal.scope_id,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )
        if not claimed_idempotency:
            replay = await container.idempotency_store.load_response(
                route="/v1/jobs",
                scope_id=principal.scope_id,
                idempotency_key=idempotency_key,
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
            job = await container.job_service.enqueue(
                job_type=payload.job_type,
                payload=payload.payload,
                scope_id=principal.scope_id,
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
        if idempotency_key is not None and claimed_idempotency:
            await container.idempotency_store.discard_claim(
                route="/v1/jobs",
                scope_id=principal.scope_id,
                idempotency_key=idempotency_key,
            )
        raise

    response = EnqueueJobResponse(job_id=job.job_id, status=job.status)
    try:
        await container.activity_store.record(
            principal=principal,
            event_type="jobs_enqueue",
        )
        container.metrics.incr("jobs_enqueue_total")
        emit_request_metric(
            container=container,
            route="jobs_enqueue",
            status="ok",
        )
        if idempotency_key is not None:
            await container.idempotency_store.store_response(
                route="/v1/jobs",
                scope_id=principal.scope_id,
                idempotency_key=idempotency_key,
                request_payload=request_payload,
                response_payload=response.model_dump(mode="json"),
            )
    except Exception as exc:
        await _record_job_failure(
            context=context,
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
            await container.idempotency_store.discard_claim(
                route="/v1/jobs",
                scope_id=principal.scope_id,
                idempotency_key=idempotency_key,
            )
        raise
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
    """
    Record metrics, structured logs, and an activity event for a job-related failure.
    
    Increments the named failure metric, emits an error route metric, logs the exception with structured fields including route and scope, and attempts to record an activity event attributing the failure to the given principal. If activity recording fails, a secondary log is emitted.
    
    Parameters:
        context (RequestContext): Request-scoped container and services.
        principal (Principal): Principal whose scope is associated with the failure.
        metric_name (str): Name of the metric to increment for this failure.
        route_metric (str): Identifier used when emitting the route-level metric.
        log_event (str): Message/event key used for the primary exception log.
        route_path (str): API route path related to the failure (included in logs).
        activity_event_type (str): Activity store event type to record for the failure.
        exc (Exception): The exception instance that triggered this failure recording.
        activity_details (str | None): Optional human-readable details to store with the activity; defaults to the exception string when omitted.
        extra (dict[str, object] | None): Optional additional structured fields to include in the primary log.
    """
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
    try:
        await container.activity_store.record(
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