from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from botocore.exceptions import BotoCoreError, ClientError
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.auth import Authenticator
from nova_file_api.config import Settings
from nova_file_api.errors import FileTransferError, queue_unavailable
from nova_file_api.jobs import (
    JobPublishError,
    JobRepository,
    JobService,
    MemoryJobPublisher,
    MemoryJobRepository,
    SqsJobPublisher,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    AuthMode,
    JobRecord,
    JobStatus,
)
from pydantic import SecretStr

from .support.app import (
    RuntimeDeps,
    build_cache_stack,
    build_runtime_deps,
    build_test_app,
)
from .support.doubles import StubAuthenticator, StubTransferService

CaptureEmf = Callable[[MetricsCollector], list[dict[str, str]]]


class _FailingPublisher:
    async def publish(self, *, job: JobRecord) -> None:
        del job
        raise JobPublishError(
            details={"error_type": "ClientError", "error_code": "Throttling"}
        )

    async def post_publish(
        self,
        *,
        job: JobRecord,
        repository: JobRepository,
        metrics: MetricsCollector,
    ) -> None:
        del job, repository, metrics
        return

    async def healthcheck(self) -> bool:
        return False


class _ConcurrentWinnerRepository(MemoryJobRepository):
    def __init__(self, *, winner_status: JobStatus) -> None:
        super().__init__()
        self._winner_status = winner_status
        self._injected = False

    async def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        if not self._injected:
            self._injected = True
            existing = await self.get(record.job_id)
            assert existing is not None
            winner = existing.model_copy(
                update={
                    "status": self._winner_status,
                    "result": {"accepted": True},
                    "error": None,
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            await super().update(winner)
        return await super().update_if_status(
            record=record,
            expected_status=expected_status,
        )


class _NeverSettlingRepository(MemoryJobRepository):
    async def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        del record, expected_status
        return False


class _TestDoubleError(RuntimeError):
    """Raised by test doubles to simulate expected control-flow failures."""


class _FlakyJobService:
    def __init__(self) -> None:
        self.calls = 0

    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        scope_id: str,
    ) -> JobRecord:
        self.calls += 1
        if self.calls == 1:
            raise queue_unavailable(  # noqa: TRY003 - explicit message asserted through API error flow
                "job enqueue failed because queue publish failed"
            )
        now = datetime.now(tz=UTC)
        return JobRecord(
            job_id=f"job-{self.calls}",
            job_type=job_type,
            scope_id=scope_id,
            status=JobStatus.PENDING,
            payload=payload,
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
        )

    async def get(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise _TestDoubleError

    async def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise _TestDoubleError


class _AlwaysFailingJobService:
    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        scope_id: str,
    ) -> JobRecord:
        del job_type, payload, scope_id
        raise _TestDoubleError

    async def get(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise _TestDoubleError

    async def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise _TestDoubleError

    async def update_result(
        self,
        *,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> JobRecord:
        del job_id, status, result, error
        raise _TestDoubleError


async def _build_same_origin_status_container(*, scope_id: str) -> RuntimeDeps:
    settings = Settings()
    settings.auth_mode = AuthMode.SAME_ORIGIN
    settings.jobs_enabled = True

    metrics = MetricsCollector(namespace="Tests")
    shared, cache = build_cache_stack()
    repository = MemoryJobRepository()
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    await repository.create(
        JobRecord(
            job_id="job-status-1",
            job_type="transform",
            scope_id=scope_id,
            status=JobStatus.PENDING,
            payload={"input": "value"},
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
    )

    return build_runtime_deps(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=Authenticator(settings=settings, cache=cache),
        transfer_service=StubTransferService(),
        job_repository=repository,
        job_service=service,
        activity_store=MemoryActivityStore(),
        idempotency_enabled=True,
    )


def _build_failing_job_container(
    *,
    worker_token: SecretStr | None = None,
) -> tuple[RuntimeDeps, MetricsCollector, MemoryActivityStore]:
    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_worker_update_token = worker_token
    metrics = MetricsCollector(namespace="Tests")
    shared, cache = build_cache_stack()
    activity_store = MemoryActivityStore()
    container = build_runtime_deps(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=StubAuthenticator(),
        transfer_service=StubTransferService(),
        job_repository=MemoryJobRepository(),
        job_service=_AlwaysFailingJobService(),
        activity_store=activity_store,
        idempotency_enabled=True,
    )
    return container, metrics, activity_store


def _job_record(*, job_id: str = "job-1") -> JobRecord:
    now = datetime.now(tz=UTC)
    return JobRecord(
        job_id=job_id,
        job_type="transform",
        scope_id="scope-1",
        status=JobStatus.PENDING,
        payload={"input": "value"},
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def capture_emf(
    monkeypatch: pytest.MonkeyPatch,
) -> CaptureEmf:
    def _patch(metrics: MetricsCollector) -> list[dict[str, str]]:
        captured_dimensions: list[dict[str, str]] = []

        def _capture_emit_emf(
            *,
            metric_name: str,
            value: float,
            unit: str,
            dimensions: dict[str, str],
        ) -> None:
            del metric_name, value, unit
            captured_dimensions.append(dimensions)

        monkeypatch.setattr(metrics, "emit_emf", _capture_emit_emf)
        return captured_dimensions

    return _patch


@pytest.mark.asyncio
async def test_sqs_job_publisher_sends_expected_queue_payload() -> None:
    captured: dict[str, Any] = {}

    class _FakeSqsClient:
        async def send_message(self, **kwargs: object) -> dict[str, str]:
            captured["send_kwargs"] = kwargs
            return {"MessageId": "1"}

    publisher = SqsJobPublisher(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/jobs",
        sqs_client=_FakeSqsClient(),
    )
    await publisher.publish(job=_job_record())

    assert captured["send_kwargs"]["QueueUrl"].endswith("/jobs")
    assert "MessageBody" in captured["send_kwargs"]


@pytest.mark.asyncio
async def test_sqs_job_publisher_maps_client_error_to_publish_error() -> None:
    class _ClientErrorSqsClient:
        async def send_message(self, **kwargs: object) -> dict[str, str]:
            del kwargs
            raise ClientError(
                error_response={
                    "Error": {"Code": "ThrottlingException"},
                },
                operation_name="SendMessage",
            )

    publisher = SqsJobPublisher(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/jobs",
        sqs_client=_ClientErrorSqsClient(),
    )

    with pytest.raises(JobPublishError) as exc:
        await publisher.publish(job=_job_record())
    assert exc.value.details["error_type"] == "ClientError"
    assert exc.value.details["error_code"] == "ThrottlingException"


@pytest.mark.asyncio
async def test_sqs_job_publisher_maps_botocore_error_to_publish_error() -> None:
    class _BotoCoreErrorSqsClient:
        async def send_message(self, **kwargs: object) -> dict[str, str]:
            del kwargs
            raise BotoCoreError()

    publisher = SqsJobPublisher(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/jobs",
        sqs_client=_BotoCoreErrorSqsClient(),
    )

    with pytest.raises(JobPublishError) as exc:
        await publisher.publish(job=_job_record())
    assert exc.value.details["error_type"] == "BotoCoreError"
    assert exc.value.details["error_code"] == "BotoCoreError"


@pytest.mark.asyncio
async def test_job_service_enqueue_marks_job_failed_when_publish_fails() -> (
    None
):
    repository = MemoryJobRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=_FailingPublisher(),
        metrics=metrics,
    )

    with pytest.raises(FileTransferError) as exc_info:
        await service.enqueue(
            job_type="transform",
            payload={"input": "value"},
            scope_id="scope-1",
        )
    assert exc_info.value.code == "queue_unavailable"
    assert exc_info.value.status_code == 503

    counters = metrics.counters_snapshot()
    assert counters["jobs_publish_failed"] == 1
    assert "jobs_enqueued" not in counters

    assert len(repository._records) == 1
    record = next(iter(repository._records.values()))
    assert record.status == JobStatus.FAILED
    assert record.error == "queue_unavailable"


@pytest.mark.asyncio
async def test_job_service_enqueue_tracks_success_counter() -> None:
    repository = MemoryJobRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )

    record = await service.enqueue(
        job_type="transform",
        payload={"input": "value"},
        scope_id="scope-1",
    )

    assert record.status == JobStatus.SUCCEEDED
    counters = metrics.counters_snapshot()
    assert counters["jobs_enqueued"] == 1
    assert counters["jobs_succeeded"] == 1
    assert "jobs_publish_failed" not in counters


@pytest.mark.asyncio
async def test_job_service_enqueue_respects_memory_toggle() -> None:
    repository = MemoryJobRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(process_immediately=False),
        metrics=metrics,
    )

    record = await service.enqueue(
        job_type="transform",
        payload={"input": "value"},
        scope_id="scope-1",
    )

    assert record.status == JobStatus.PENDING
    counters = metrics.counters_snapshot()
    assert counters["jobs_enqueued"] == 1
    assert "jobs_succeeded" not in counters
    assert "jobs_publish_failed" not in counters


@pytest.mark.asyncio
async def test_enqueue_failure_is_not_idempotency_cached() -> None:
    settings = Settings()
    settings.jobs_enabled = True
    settings.idempotency_enabled = True

    metrics = MetricsCollector(namespace="Tests")
    shared, cache = build_cache_stack()
    job_service = _FlakyJobService()

    container = build_runtime_deps(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=StubAuthenticator(),
        transfer_service=StubTransferService(),
        job_repository=MemoryJobRepository(),
        job_service=job_service,
        activity_store=MemoryActivityStore(),
        idempotency_enabled=True,
    )

    app = build_test_app(container)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        first = await client.post(
            "/v1/jobs",
            headers={"Idempotency-Key": "job-failure-key"},
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
        second = await client.post(
            "/v1/jobs",
            headers={"Idempotency-Key": "job-failure-key"},
            json={"job_type": "transform", "payload": {"input": "a"}},
        )

    assert first.status_code == 503
    assert first.json()["error"]["code"] == "queue_unavailable"
    assert second.status_code == 200
    assert job_service.calls == 2


@pytest.mark.asyncio
async def test_job_service_update_result_updates_job_status() -> None:
    repository = MemoryJobRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    pending = JobRecord(
        job_id="job-update-1",
        job_type="transform",
        scope_id="scope-1",
        status=JobStatus.PENDING,
        payload={"input": "value"},
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    await repository.create(pending)

    updated = await service.update_result(
        job_id="job-update-1",
        status=JobStatus.RUNNING,
        result=None,
        error=None,
    )

    assert updated.status == JobStatus.RUNNING
    counters = metrics.counters_snapshot()
    assert counters["jobs_running"] == 1
    assert counters["jobs_worker_result_updates_total"] == 1
    assert counters["jobs_worker_result_updates_running"] == 1
    latencies = metrics.latency_snapshot()
    assert "jobs_queue_lag_ms" in latencies
    assert latencies["jobs_queue_lag_ms"] >= 0.0


@pytest.mark.asyncio
async def test_job_service_update_result_observes_queue_lag_ms() -> None:
    repository = MemoryJobRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    created_at = datetime.now(tz=UTC) - timedelta(seconds=2)
    pending = JobRecord(
        job_id="job-update-5",
        job_type="transform",
        scope_id="scope-1",
        status=JobStatus.PENDING,
        payload={"input": "value"},
        result=None,
        error=None,
        created_at=created_at,
        updated_at=created_at,
    )
    await repository.create(pending)

    await service.update_result(
        job_id="job-update-5",
        status=JobStatus.RUNNING,
        result=None,
        error=None,
    )

    latencies = metrics.latency_snapshot()
    assert latencies["jobs_queue_lag_ms"] >= 1500.0


@pytest.mark.asyncio
async def test_job_service_allows_idempotent_terminal_result_update() -> None:
    repository = MemoryJobRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    succeeded = JobRecord(
        job_id="job-update-4",
        job_type="transform",
        scope_id="scope-1",
        status=JobStatus.SUCCEEDED,
        payload={"input": "value"},
        result={"ok": True},
        error=None,
        created_at=now,
        updated_at=now,
    )
    await repository.create(succeeded)

    updated = await service.update_result(
        job_id="job-update-4",
        status=JobStatus.SUCCEEDED,
        result=None,
        error=None,
    )

    assert updated.status == JobStatus.SUCCEEDED
    assert updated.result == {"ok": True}


@pytest.mark.asyncio
async def test_job_service_update_result_clears_error_on_succeeded() -> None:
    repository = MemoryJobRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    running = JobRecord(
        job_id="job-update-6",
        job_type="transform",
        scope_id="scope-1",
        status=JobStatus.RUNNING,
        payload={"input": "value"},
        result={"previous": True},
        error="worker_failed",
        created_at=now,
        updated_at=now,
    )
    await repository.create(running)

    updated = await service.update_result(
        job_id="job-update-6",
        status=JobStatus.SUCCEEDED,
        result={"accepted": True},
        error="stale_error",
    )

    assert updated.status == JobStatus.SUCCEEDED
    assert updated.result == {"accepted": True}
    assert updated.error is None


@pytest.mark.asyncio
async def test_job_service_update_result_rejects_invalid_transition() -> None:
    repository = MemoryJobRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    failed = JobRecord(
        job_id="job-update-2",
        job_type="transform",
        scope_id="scope-1",
        status=JobStatus.FAILED,
        payload={"input": "value"},
        result=None,
        error="worker_failed",
        created_at=now,
        updated_at=now,
    )
    await repository.create(failed)

    with pytest.raises(FileTransferError) as excinfo:
        await service.update_result(
            job_id="job-update-2",
            status=JobStatus.SUCCEEDED,
            result={"ok": True},
            error=None,
        )
    assert excinfo.value.code == "conflict"
    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_job_service_result_update_conflicts_on_stale() -> None:
    repository = _ConcurrentWinnerRepository(winner_status=JobStatus.SUCCEEDED)
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    pending = JobRecord(
        job_id="job-update-race-1",
        job_type="transform",
        scope_id="scope-1",
        status=JobStatus.PENDING,
        payload={"input": "value"},
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    await repository.create(pending)

    with pytest.raises(FileTransferError) as excinfo:
        await service.update_result(
            job_id="job-update-race-1",
            status=JobStatus.FAILED,
            result=None,
            error="worker_failed",
        )

    assert excinfo.value.code == "conflict"
    latest = await repository.get("job-update-race-1")
    assert latest is not None
    assert latest.status == JobStatus.SUCCEEDED
    counters = metrics.counters_snapshot()
    assert "jobs_failed" not in counters
    assert "jobs_worker_result_updates_failed" not in counters


@pytest.mark.asyncio
async def test_job_service_cancel_keeps_concurrent_terminal_state() -> None:
    repository = _ConcurrentWinnerRepository(winner_status=JobStatus.SUCCEEDED)
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    pending = JobRecord(
        job_id="job-cancel-race-1",
        job_type="transform",
        scope_id="scope-1",
        status=JobStatus.PENDING,
        payload={"input": "value"},
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    await repository.create(pending)

    returned = await service.cancel(
        job_id="job-cancel-race-1",
        scope_id="scope-1",
    )

    assert returned.status == JobStatus.SUCCEEDED
    assert returned.result == {"accepted": True}
    counters = metrics.counters_snapshot()
    assert "jobs_canceled" not in counters


@pytest.mark.asyncio
async def test_job_service_cancel_conflicts_after_retry_limit() -> None:
    repository = _NeverSettlingRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    await repository.create(
        JobRecord(
            job_id="job-cancel-never-settles",
            job_type="transform",
            scope_id="scope-1",
            status=JobStatus.PENDING,
            payload={"input": "value"},
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
    )

    with pytest.raises(FileTransferError) as excinfo:
        await service.cancel(
            job_id="job-cancel-never-settles",
            scope_id="scope-1",
        )

    assert excinfo.value.code == "conflict"
    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_update_job_result_requires_valid_worker_token() -> None:
    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_worker_update_token = SecretStr("test-worker-token")

    metrics = MetricsCollector(namespace="Tests")
    shared, cache = build_cache_stack()
    repository = MemoryJobRepository()
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    await repository.create(
        JobRecord(
            job_id="job-update-3",
            job_type="transform",
            scope_id="scope-1",
            status=JobStatus.PENDING,
            payload={"input": "value"},
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
    )

    container = build_runtime_deps(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=StubAuthenticator(),
        transfer_service=StubTransferService(),
        job_repository=repository,
        job_service=service,
        activity_store=MemoryActivityStore(),
        idempotency_enabled=True,
    )

    app = build_test_app(container)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        forbidden_response = await client.post(
            "/v1/internal/jobs/job-update-3/result",
            headers={"X-Worker-Token": "wrong-token"},
            json={"status": "running"},
        )
        ok_response = await client.post(
            "/v1/internal/jobs/job-update-3/result",
            headers={"X-Worker-Token": "test-worker-token"},
            json={"status": "succeeded", "result": {"accepted": True}},
        )

    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["error"]["code"] == "forbidden"
    assert ok_response.status_code == 200
    assert ok_response.json()["status"] == "succeeded"
    activity_summary = await container.activity_store.summary()
    assert activity_summary["events_total"] == 1
    assert activity_summary["distinct_event_types"] == 1
    assert activity_summary["active_users_today"] == 1


@pytest.mark.asyncio
async def test_get_job_status_failure_emits_error_observability(
    capture_emf: CaptureEmf,
) -> None:
    container, metrics, activity_store = _build_failing_job_container()
    emitted_dimensions = capture_emf(metrics)
    app = build_test_app(container)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.get("/v1/jobs/job-status-1")

    assert response.status_code == 500
    counters = metrics.counters_snapshot()
    assert counters["jobs_status_failure_total"] == 1
    assert {"route": "jobs_status", "status": "error"} in emitted_dimensions
    activity_summary = await activity_store.summary()
    assert activity_summary["events_total"] == 1
    assert activity_summary["distinct_event_types"] == 1
    assert activity_summary["active_users_today"] == 1


@pytest.mark.asyncio
async def test_legacy_cancel_route_is_not_exposed() -> None:
    """Verify legacy cancel route is not exposed and returns 404."""
    app = build_test_app(
        await _build_same_origin_status_container(scope_id="scope-legacy")
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.post("/api/jobs/job-status-1/cancel")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_job_failure_emits_error_observability(
    capture_emf: CaptureEmf,
) -> None:
    """Verify cancel failures emit metrics and observability dimensions."""
    container, metrics, activity_store = _build_failing_job_container()
    emitted_dimensions = capture_emf(metrics)
    app = build_test_app(container)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.post("/v1/jobs/job-status-1/cancel")

    assert response.status_code == 500
    counters = metrics.counters_snapshot()
    assert counters["jobs_cancel_failure_total"] == 1
    assert {"route": "jobs_cancel", "status": "error"} in emitted_dimensions
    activity_summary = await activity_store.summary()
    assert activity_summary["events_total"] == 1
    assert activity_summary["distinct_event_types"] == 1
    assert activity_summary["active_users_today"] == 1


@pytest.mark.asyncio
async def test_update_job_result_failure_emits_error_observability(
    capture_emf: CaptureEmf,
) -> None:
    container, metrics, activity_store = _build_failing_job_container(
        worker_token=SecretStr("test-worker-token")
    )
    emitted_dimensions = capture_emf(metrics)
    app = build_test_app(container)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.post(
            "/v1/internal/jobs/job-update-4/result",
            headers={"X-Worker-Token": "test-worker-token"},
            json={"status": "running"},
        )

    assert response.status_code == 500
    counters = metrics.counters_snapshot()
    assert counters["jobs_result_update_failure_total"] == 1
    assert {
        "route": "jobs_result_update",
        "status": "error",
    } in emitted_dimensions
    activity_summary = await activity_store.summary()
    assert activity_summary["events_total"] == 1
    assert activity_summary["distinct_event_types"] == 1
    assert activity_summary["active_users_today"] == 1


@pytest.mark.asyncio
async def test_get_job_status_accepts_scope_header_same_origin() -> None:
    container = await _build_same_origin_status_container(
        scope_id="scope-header"
    )
    app = build_test_app(container)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.get(
            "/v1/jobs/job-status-1",
            headers={"X-Session-Id": "scope-header"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["job_id"] == "job-status-1"
    assert payload["job"]["scope_id"] == "scope-header"


@pytest.mark.asyncio
async def test_get_job_status_requires_session_scope_in_same_origin_mode() -> (
    None
):
    container = await _build_same_origin_status_container(
        scope_id="scope-header"
    )
    app = build_test_app(container)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.get("/v1/jobs/job-status-1")

    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "unauthorized"
    assert payload["error"]["message"] == "missing session scope"
