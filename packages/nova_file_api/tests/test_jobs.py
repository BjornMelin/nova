from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_app
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
    JobService,
    MemoryJobPublisher,
    MemoryJobRepository,
    SqsJobPublisher,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import JobRecord, JobStatus, Principal
from botocore.exceptions import BotoCoreError, ClientError
from fastapi.testclient import TestClient
from starlette.requests import Request


class _StubAuthenticator:
    async def authenticate(
        self,
        *,
        request: Request,
        session_id: str | None,
    ) -> Principal:
        del request, session_id
        return Principal(
            subject="user-1",
            scope_id="scope-1",
            tenant_id=None,
            scopes=(),
            permissions=("metrics:read",),
        )


class _StubTransferService:
    pass


class _FailingPublisher:
    def publish(self, *, job: JobRecord) -> None:
        del job
        raise JobPublishError(
            details={"error_type": "ClientError", "error_code": "Throttling"}
        )


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
            raise queue_unavailable(
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
        raise RuntimeError("not used by this test")

    def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise RuntimeError("not used by this test")


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


def test_sqs_job_publisher_configures_retry_mode_and_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeSqsClient:
        def send_message(self, **kwargs: Any) -> dict[str, str]:
            captured["send_kwargs"] = kwargs
            return {"MessageId": "1"}

    def _fake_client(service_name: str, **kwargs: Any) -> _FakeSqsClient:
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
        def send_message(self, **kwargs: Any) -> dict[str, str]:
            del kwargs
            raise ClientError(
                error_response={
                    "Error": {"Code": "ThrottlingException"},
                },
                operation_name="SendMessage",
            )

    def _fake_client(service_name: str, **kwargs: Any) -> _ClientErrorSqsClient:
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
        def send_message(self, **kwargs: Any) -> dict[str, str]:
            del kwargs
            raise BotoCoreError()

    def _fake_client(
        service_name: str,
        **kwargs: Any,
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

    try:
        service.enqueue(
            job_type="transform",
            payload={"input": "value"},
            scope_id="scope-1",
        )
    except FileTransferError as exc:
        assert exc.code == "queue_unavailable"
        assert exc.status_code == 503
    else:
        raise AssertionError("expected enqueue to raise queue_unavailable")

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
        authenticator=_StubAuthenticator(),  # type: ignore[arg-type]
        transfer_service=_StubTransferService(),  # type: ignore[arg-type]
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
            "/api/jobs/enqueue",
            headers={"Idempotency-Key": "job-failure-key"},
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
        second = client.post(
            "/api/jobs/enqueue",
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
    assert latencies["jobs_queue_lag_ms"] >= 1900.0


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

    try:
        service.update_result(
            job_id="job-update-2",
            status=JobStatus.SUCCEEDED,
            result={"ok": True},
            error=None,
        )
    except FileTransferError as exc:
        assert exc.code == "conflict"
        assert exc.status_code == 409
    else:
        raise AssertionError("expected invalid terminal transition to fail")


def test_update_job_result_requires_valid_worker_token() -> None:
    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_worker_update_token = "test-worker-token"

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
        authenticator=_StubAuthenticator(),  # type: ignore[arg-type]
        transfer_service=_StubTransferService(),  # type: ignore[arg-type]
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
            "/api/jobs/job-update-3/result",
            headers={"X-Worker-Token": "wrong-token"},
            json={"status": "running"},
        )
        ok_response = client.post(
            "/api/jobs/job-update-3/result",
            headers={"X-Worker-Token": "test-worker-token"},
            json={"status": "succeeded", "result": {"accepted": True}},
        )

    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["error"]["code"] == "forbidden"
    assert ok_response.status_code == 200
    assert ok_response.json()["status"] == "succeeded"
