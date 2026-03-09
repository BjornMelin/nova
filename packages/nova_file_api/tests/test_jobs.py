from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from botocore.exceptions import BotoCoreError, ClientError
from fastapi.testclient import TestClient
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_app
from nova_file_api.auth import Authenticator
from nova_file_api.cache import (
    LocalTTLCache,
    SharedRedisCache,
    TwoTierCache,
)
from nova_file_api.config import Settings
from nova_file_api.container import AppContainer
from nova_file_api.errors import FileTransferError, queue_unavailable
from nova_file_api.idempotency import IdempotencyStore
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

from ._test_doubles import StubAuthenticator, StubTransferService

CaptureEmf = Callable[[MetricsCollector], list[dict[str, str]]]


class _FailingPublisher:
    def publish(self, *, job: JobRecord) -> None:
        del job
        raise JobPublishError(
            details={"error_type": "ClientError", "error_code": "Throttling"}
        )

    def post_publish(
        self,
        *,
        job: JobRecord,
        repository: JobRepository,
        metrics: MetricsCollector,
    ) -> None:
        del job, repository, metrics
        return

    def healthcheck(self) -> bool:
        return False


class _ConcurrentWinnerRepository(MemoryJobRepository):
    def __init__(self, *, winner_status: JobStatus) -> None:
        super().__init__()
        self._winner_status = winner_status
        self._injected = False

    def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        if not self._injected:
            self._injected = True
            existing = self.get(record.job_id)
            assert existing is not None
            winner = existing.model_copy(
                update={
                    "status": self._winner_status,
                    "result": {"accepted": True},
                    "error": None,
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            super().update(winner)
        return super().update_if_status(
            record=record,
            expected_status=expected_status,
        )


class _NeverSettlingRepository(MemoryJobRepository):
    def update_if_status(
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

    def enqueue(
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

    def get(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise _TestDoubleError

    def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise _TestDoubleError


class _AlwaysFailingJobService:
    def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        scope_id: str,
    ) -> JobRecord:
        del job_type, payload, scope_id
        raise _TestDoubleError

    def get(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise _TestDoubleError

    def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise _TestDoubleError

    def update_result(
        self,
        *,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> JobRecord:
        del job_id, status, result, error
        raise _TestDoubleError


def _build_same_origin_status_container(*, scope_id: str) -> AppContainer:
    settings = Settings()
    settings.auth_mode = AuthMode.SAME_ORIGIN
    settings.jobs_enabled = True

    metrics = MetricsCollector(namespace="Tests")
    shared = SharedRedisCache(url=None)
    cache = TwoTierCache(
        local=LocalTTLCache(ttl_seconds=60, max_entries=128),
        shared=shared,
        shared_ttl_seconds=60,
    )
    repository = MemoryJobRepository()
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    repository.create(
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

    return AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=Authenticator(settings=settings, cache=cache),
        transfer_service=StubTransferService(),  # type: ignore[arg-type]
        job_repository=repository,
        job_service=service,
        activity_store=MemoryActivityStore(),
        idempotency_store=IdempotencyStore(
            cache=cache,
            enabled=True,
            ttl_seconds=300,
        ),
    )


def _build_failing_job_container(
    *,
    worker_token: SecretStr | None = None,
) -> tuple[AppContainer, MetricsCollector, MemoryActivityStore]:
    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_worker_update_token = worker_token
    metrics = MetricsCollector(namespace="Tests")
    shared = SharedRedisCache(url=None)
    cache = TwoTierCache(
        local=LocalTTLCache(ttl_seconds=60, max_entries=128),
        shared=shared,
        shared_ttl_seconds=60,
    )
    activity_store = MemoryActivityStore()
    container = AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=StubAuthenticator(),  # type: ignore[arg-type]
        transfer_service=StubTransferService(),  # type: ignore[arg-type]
        job_repository=MemoryJobRepository(),
        job_service=_AlwaysFailingJobService(),  # type: ignore[arg-type]
        activity_store=activity_store,
        idempotency_store=IdempotencyStore(
            cache=cache,
            enabled=True,
            ttl_seconds=300,
        ),
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


def test_sqs_job_publisher_configures_retry_mode_and_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeSqsClient:
        def send_message(self, **kwargs: object) -> dict[str, str]:
            captured["send_kwargs"] = kwargs
            return {"MessageId": "1"}

    def _fake_client(service_name: str, **kwargs: object) -> _FakeSqsClient:
        captured["service_name"] = service_name
        captured["kwargs"] = kwargs
        return _FakeSqsClient()

    monkeypatch.setattr("nova_file_api.jobs.boto3.client", _fake_client)
    publisher = SqsJobPublisher(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/jobs",
        retry_mode="adaptive",
        retry_total_max_attempts=7,
    )
    publisher.publish(job=_job_record())

    assert captured["service_name"] == "sqs"
    config = captured["kwargs"]["config"]
    assert config.retries is not None
    assert config.retries["mode"] == "adaptive"
    assert config.retries["total_max_attempts"] == 7
    assert captured["send_kwargs"]["QueueUrl"].endswith("/jobs")


def test_sqs_job_publisher_maps_client_error_to_publish_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ClientErrorSqsClient:
        def send_message(self, **kwargs: object) -> dict[str, str]:
            del kwargs
            raise ClientError(
                error_response={
                    "Error": {"Code": "ThrottlingException"},
                },
                operation_name="SendMessage",
            )

    def _fake_client(
        service_name: str, **kwargs: object
    ) -> _ClientErrorSqsClient:
        del service_name, kwargs
        return _ClientErrorSqsClient()

    monkeypatch.setattr("nova_file_api.jobs.boto3.client", _fake_client)
    publisher = SqsJobPublisher(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/jobs",
    )

    with pytest.raises(JobPublishError) as exc:
        publisher.publish(job=_job_record())
    assert exc.value.details["error_type"] == "ClientError"
    assert exc.value.details["error_code"] == "ThrottlingException"


def test_sqs_job_publisher_maps_botocore_error_to_publish_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BotoCoreErrorSqsClient:
        def send_message(self, **kwargs: object) -> dict[str, str]:
            del kwargs
            raise BotoCoreError()

    def _fake_client(
        service_name: str,
        **kwargs: object,
    ) -> _BotoCoreErrorSqsClient:
        del service_name, kwargs
        return _BotoCoreErrorSqsClient()

    monkeypatch.setattr("nova_file_api.jobs.boto3.client", _fake_client)
    publisher = SqsJobPublisher(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/jobs",
    )

    with pytest.raises(JobPublishError) as exc:
        publisher.publish(job=_job_record())
    assert exc.value.details["error_type"] == "BotoCoreError"
    assert exc.value.details["error_code"] == "BotoCoreError"


def test_job_service_enqueue_marks_job_failed_when_publish_fails() -> None:
    repository = MemoryJobRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=_FailingPublisher(),
        metrics=metrics,
    )

    with pytest.raises(FileTransferError) as exc_info:
        service.enqueue(
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


def test_job_service_enqueue_tracks_success_counter() -> None:
    repository = MemoryJobRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )

    record = service.enqueue(
        job_type="transform",
        payload={"input": "value"},
        scope_id="scope-1",
    )

    assert record.status == JobStatus.SUCCEEDED
    counters = metrics.counters_snapshot()
    assert counters["jobs_enqueued"] == 1
    assert counters["jobs_succeeded"] == 1
    assert "jobs_publish_failed" not in counters


def test_job_service_enqueue_respects_memory_toggle() -> None:
    repository = MemoryJobRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(process_immediately=False),
        metrics=metrics,
    )

    record = service.enqueue(
        job_type="transform",
        payload={"input": "value"},
        scope_id="scope-1",
    )

    assert record.status == JobStatus.PENDING
    counters = metrics.counters_snapshot()
    assert counters["jobs_enqueued"] == 1
    assert "jobs_succeeded" not in counters
    assert "jobs_publish_failed" not in counters


def test_enqueue_failure_is_not_idempotency_cached() -> None:
    settings = Settings()
    settings.jobs_enabled = True
    settings.idempotency_enabled = True

    metrics = MetricsCollector(namespace="Tests")
    shared = SharedRedisCache(url=None)
    cache = TwoTierCache(
        local=LocalTTLCache(ttl_seconds=60, max_entries=128),
        shared=shared,
        shared_ttl_seconds=60,
    )
    job_service = _FlakyJobService()

    container = AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=StubAuthenticator(),  # type: ignore[arg-type]
        transfer_service=StubTransferService(),  # type: ignore[arg-type]
        job_repository=MemoryJobRepository(),
        job_service=job_service,  # type: ignore[arg-type]
        activity_store=MemoryActivityStore(),
        idempotency_store=IdempotencyStore(
            cache=cache,
            enabled=True,
            ttl_seconds=300,
        ),
    )

    app = create_app(container_override=container)
    with TestClient(app) as client:
        first = client.post(
            "/v1/jobs",
            headers={"Idempotency-Key": "job-failure-key"},
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
        second = client.post(
            "/v1/jobs",
            headers={"Idempotency-Key": "job-failure-key"},
            json={"job_type": "transform", "payload": {"input": "a"}},
        )

    assert first.status_code == 503
    assert first.json()["error"]["code"] == "queue_unavailable"
    assert second.status_code == 200
    assert job_service.calls == 2


def test_job_service_update_result_updates_job_status() -> None:
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
    repository.create(pending)

    updated = service.update_result(
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


def test_job_service_update_result_observes_queue_lag_ms() -> None:
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
    repository.create(pending)

    service.update_result(
        job_id="job-update-5",
        status=JobStatus.RUNNING,
        result=None,
        error=None,
    )

    latencies = metrics.latency_snapshot()
    assert latencies["jobs_queue_lag_ms"] >= 1500.0


def test_job_service_update_result_allows_idempotent_terminal_update() -> None:
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
    repository.create(succeeded)

    updated = service.update_result(
        job_id="job-update-4",
        status=JobStatus.SUCCEEDED,
        result=None,
        error=None,
    )

    assert updated.status == JobStatus.SUCCEEDED
    assert updated.result == {"ok": True}


def test_job_service_update_result_clears_error_on_succeeded() -> None:
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
    repository.create(running)

    updated = service.update_result(
        job_id="job-update-6",
        status=JobStatus.SUCCEEDED,
        result={"accepted": True},
        error="stale_error",
    )

    assert updated.status == JobStatus.SUCCEEDED
    assert updated.result == {"accepted": True}
    assert updated.error is None


def test_job_service_update_result_rejects_invalid_transition() -> None:
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
    repository.create(failed)

    with pytest.raises(FileTransferError) as excinfo:
        service.update_result(
            job_id="job-update-2",
            status=JobStatus.SUCCEEDED,
            result={"ok": True},
            error=None,
        )
    assert excinfo.value.code == "conflict"
    assert excinfo.value.status_code == 409


def test_job_service_update_result_conflicts_on_stale_worker_transition() -> (
    None
):
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
    repository.create(pending)

    with pytest.raises(FileTransferError) as excinfo:
        service.update_result(
            job_id="job-update-race-1",
            status=JobStatus.FAILED,
            result=None,
            error="worker_failed",
        )

    assert excinfo.value.code == "conflict"
    latest = repository.get("job-update-race-1")
    assert latest is not None
    assert latest.status == JobStatus.SUCCEEDED
    counters = metrics.counters_snapshot()
    assert "jobs_failed" not in counters
    assert "jobs_worker_result_updates_failed" not in counters


def test_job_service_cancel_does_not_clobber_concurrent_terminal_state() -> (
    None
):
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
    repository.create(pending)

    returned = service.cancel(job_id="job-cancel-race-1", scope_id="scope-1")

    assert returned.status == JobStatus.SUCCEEDED
    assert returned.result == {"accepted": True}
    counters = metrics.counters_snapshot()
    assert "jobs_canceled" not in counters


def test_job_service_cancel_conflicts_after_retry_limit() -> None:
    repository = _NeverSettlingRepository()
    metrics = MetricsCollector(namespace="Tests")
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    repository.create(
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
        service.cancel(job_id="job-cancel-never-settles", scope_id="scope-1")

    assert excinfo.value.code == "conflict"
    assert excinfo.value.status_code == 409


def test_update_job_result_requires_valid_worker_token() -> None:
    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_worker_update_token = SecretStr("test-worker-token")

    metrics = MetricsCollector(namespace="Tests")
    shared = SharedRedisCache(url=None)
    cache = TwoTierCache(
        local=LocalTTLCache(ttl_seconds=60, max_entries=128),
        shared=shared,
        shared_ttl_seconds=60,
    )
    repository = MemoryJobRepository()
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=metrics,
    )
    now = datetime.now(tz=UTC)
    repository.create(
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

    container = AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=StubAuthenticator(),  # type: ignore[arg-type]
        transfer_service=StubTransferService(),  # type: ignore[arg-type]
        job_repository=repository,
        job_service=service,
        activity_store=MemoryActivityStore(),
        idempotency_store=IdempotencyStore(
            cache=cache,
            enabled=True,
            ttl_seconds=300,
        ),
    )

    app = create_app(container_override=container)
    with TestClient(app) as client:
        forbidden_response = client.post(
            "/v1/internal/jobs/job-update-3/result",
            headers={"X-Worker-Token": "wrong-token"},
            json={"status": "running"},
        )
        ok_response = client.post(
            "/v1/internal/jobs/job-update-3/result",
            headers={"X-Worker-Token": "test-worker-token"},
            json={"status": "succeeded", "result": {"accepted": True}},
        )

    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["error"]["code"] == "forbidden"
    assert ok_response.status_code == 200
    assert ok_response.json()["status"] == "succeeded"
    summary = container.activity_store.summary()
    assert summary["events_total"] == 1
    assert summary["distinct_event_types"] == 1
    assert summary["active_users_today"] == 1


def test_get_job_status_failure_emits_error_observability(
    capture_emf: CaptureEmf,
) -> None:
    container, metrics, activity_store = _build_failing_job_container()
    emitted_dimensions = capture_emf(metrics)
    app = create_app(container_override=container)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/v1/jobs/job-status-1")

    assert response.status_code == 500
    counters = metrics.counters_snapshot()
    assert counters["jobs_status_failure_total"] == 1
    assert {"route": "jobs_status", "status": "error"} in emitted_dimensions
    summary = activity_store.summary()
    assert summary["events_total"] == 1
    assert summary["distinct_event_types"] == 1
    assert summary["active_users_today"] == 1


def test_legacy_cancel_route_is_not_exposed() -> None:
    """Verify legacy cancel route is not exposed and returns 404."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/jobs/job-status-1/cancel")

    assert response.status_code == 404


def test_cancel_job_failure_emits_error_observability(
    capture_emf: CaptureEmf,
) -> None:
    """Verify cancel failures emit metrics and observability dimensions."""
    container, metrics, activity_store = _build_failing_job_container()
    emitted_dimensions = capture_emf(metrics)
    app = create_app(container_override=container)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/v1/jobs/job-status-1/cancel")

    assert response.status_code == 500
    counters = metrics.counters_snapshot()
    assert counters["jobs_cancel_failure_total"] == 1
    assert {"route": "jobs_cancel", "status": "error"} in emitted_dimensions
    summary = activity_store.summary()
    assert summary["events_total"] == 1
    assert summary["distinct_event_types"] == 1
    assert summary["active_users_today"] == 1


def test_update_job_result_failure_emits_error_observability(
    capture_emf: CaptureEmf,
) -> None:
    container, metrics, activity_store = _build_failing_job_container(
        worker_token=SecretStr("test-worker-token")
    )
    emitted_dimensions = capture_emf(metrics)
    app = create_app(container_override=container)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
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
    summary = activity_store.summary()
    assert summary["events_total"] == 1
    assert summary["distinct_event_types"] == 1
    assert summary["active_users_today"] == 1


def test_get_job_status_accepts_scope_header_same_origin() -> None:
    container = _build_same_origin_status_container(scope_id="scope-header")
    app = create_app(container_override=container)
    with TestClient(app) as client:
        response = client.get(
            "/v1/jobs/job-status-1",
            headers={"X-Session-Id": "scope-header"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["job_id"] == "job-status-1"
    assert payload["job"]["scope_id"] == "scope-header"


def test_get_job_status_requires_session_scope_in_same_origin_mode() -> None:
    container = _build_same_origin_status_container(scope_id="scope-header")
    app = create_app(container_override=container)
    with TestClient(app) as client:
        response = client.get("/v1/jobs/job-status-1")

    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "unauthorized"
    assert payload["error"]["message"] == "missing session scope"
