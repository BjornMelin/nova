from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

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
    async def publish(self, *, job: JobRecord) -> None:
        """
        Simulates a publisher that always fails with a throttling client error.
        
        Raises:
            JobPublishError: Always raised with details {"error_type": "ClientError", "error_code": "Throttling"}.
        """
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
        """
        No-op post-publish hook that fulfills the publisher interface.
        
        Accepts the published `job`, the `repository`, and `metrics` but performs no action.
        """
        del job, repository, metrics
        return

    async def healthcheck(self) -> bool:
        """
        Report whether the publisher is healthy.
        
        This test publisher always reports itself as unhealthy.
        
        Returns:
            `False` indicating the publisher is not healthy.
        """
        return False


class _ConcurrentWinnerRepository(MemoryJobRepository):
    def __init__(self, *, winner_status: JobStatus) -> None:
        """
        Create a repository that injects a predetermined terminal status on the first conditional update attempt.
        
        Parameters:
            winner_status (JobStatus): Terminal status to apply to the job the first time update_if_status is called.
        """
        super().__init__()
        self._winner_status = winner_status
        self._injected = False

    async def update_if_status(
        self,
        *,
        record: JobRecord,
        expected_status: JobStatus,
    ) -> bool:
        """
        Simulates a concurrent winner by injecting a terminal update on first invocation, then performs the conditional update.
        
        On the first call only, the repository is modified so the stored job is moved to the configured winner status with result {"accepted": True} and no error; after that the function attempts the conditional update against the provided record and expected_status. Subsequent calls perform the conditional update without injecting a winner.
        
        Parameters:
            record (JobRecord): The job record to update conditionally.
            expected_status (JobStatus): The status that must match the current record for the conditional update to succeed.
        
        Returns:
            `true` if the conditional update succeeded (record matched expected_status and was updated), `false` otherwise.
        """
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
        """
        Simulate a repository that never accepts status updates.
        
        This method ignores `record` and `expected_status` and always reports the conditional update failed.
        
        Returns:
            `False` indicating the repository did not apply the update.
        """
        del record, expected_status
        return False


class _TestDoubleError(RuntimeError):
    """Raised by test doubles to simulate expected control-flow failures."""


class _FlakyJobService:
    def __init__(self) -> None:
        """
        Initialize a flaky job service test double and its internal call counter.
        
        Sets self.calls to 0 to track how many times enqueue has been invoked.
        """
        self.calls = 0

    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        scope_id: str,
    ) -> JobRecord:
        """
        Simulate enqueueing a job that fails on the first call and succeeds on subsequent calls.
        
        On the first invocation this function raises a queue_unavailable error to emulate a transient publish failure; on later calls it returns a newly created JobRecord with status PENDING, a job_id formatted as "job-{n}" where n is the call count, and created_at/updated_at set to the current UTC time.
        
        Parameters:
            job_type (str): Type identifier for the job.
            payload (dict[str, Any]): Job payload.
            scope_id (str): Scope identifier for the job.
        
        Returns:
            JobRecord: The created job record with status PENDING and timestamps set to now.
        
        Raises:
            queue_unavailable: Emitted on the first call to simulate a queue publish failure.
        """
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
        """
        Simulated job retrieval that always fails for testing.
        
        Always raises _TestDoubleError to signal a controlled test failure when invoked.
        
        Raises:
            _TestDoubleError: Always raised to simulate an error from the job service.
        """
        del job_id, scope_id
        raise _TestDoubleError

    async def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        """
        Simulate a cancellation operation that always fails for testing.
        
        Raises:
            _TestDoubleError: Always raised to simulate an internal failure during cancel.
        """
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
        """
        Simulate a failing enqueue operation for tests.
        
        Raises:
            _TestDoubleError: Raised to simulate an enqueue failure from the job service.
        """
        del job_type, payload, scope_id
        raise _TestDoubleError

    async def get(self, *, job_id: str, scope_id: str) -> JobRecord:
        """
        Simulated job retrieval that always fails for testing.
        
        Always raises _TestDoubleError to signal a controlled test failure when invoked.
        
        Raises:
            _TestDoubleError: Always raised to simulate an error from the job service.
        """
        del job_id, scope_id
        raise _TestDoubleError

    async def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        """
        Simulate a cancellation operation that always fails for testing.
        
        Raises:
            _TestDoubleError: Always raised to simulate an internal failure during cancel.
        """
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
        """
        Test double that simulates a failing job update by ignoring inputs and always raising _TestDoubleError.
        
        This method does not return a JobRecord; it deterministically raises to signal a controlled test failure.
        
        Raises:
            _TestDoubleError: Raised unconditionally to simulate an error from the job service.
        """
        del job_id, status, result, error
        raise _TestDoubleError


def _build_same_origin_status_container(*, scope_id: str) -> AppContainer:
    """
    Builds an application container configured for same-origin job status tests.
    
    Creates settings with SAME_ORIGIN auth and jobs enabled, a metrics collector,
    two-tier cache (local + shared), an in-memory job repository pre-populated
    with a pending JobRecord having id "job-status-1" and the given scope_id, and
    test doubles for authenticator, transfer service, activity store, and idempotency.
    
    Parameters:
        scope_id (str): Scope identifier to assign to the pre-populated job record.
    
    Returns:
        AppContainer: Fully initialized container ready for testing same-origin job status endpoints.
    """
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
    repository._records["job-status-1"] = JobRecord(
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
    """
    Create and return a test helper that patches a MetricsCollector to capture emitted EMF metric dimensions.
    
    Parameters:
        monkeypatch (pytest.MonkeyPatch): pytest monkeypatch fixture used to replace the collector's emit_emf method.
    
    Returns:
        capture_emf (Callable[[MetricsCollector], list[dict[str, str]]]): A function that, when called with a MetricsCollector, patches its `emit_emf` to append each emission's `dimensions` dict to a list and returns that list for inspection in tests.
    """
    def _patch(metrics: MetricsCollector) -> list[dict[str, str]]:
        """
        Capture EMF metric dimensions emitted by a MetricsCollector by patching its `emit_emf` method.
        
        The function patches `metrics.emit_emf` so emitted metric calls append their `dimensions` dict to the returned list.
        
        Returns:
            captured_dimensions (list[dict[str, str]]): A list that will be populated with the `dimensions` dictionaries supplied to `emit_emf`.
        """
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
    """
    Verifies that SqsJobPublisher sends a message to the configured jobs queue and includes a MessageBody.
    
    Sets up a fake SQS client to capture send_message keyword arguments, publishes a job, and asserts the captured QueueUrl ends with "/jobs" and that a MessageBody was provided.
    """
    captured: dict[str, Any] = {}

    class _FakeSqsClient:
        async def send_message(self, **kwargs: object) -> dict[str, str]:
            """
            Record the provided send-message keyword arguments for test inspection.
            
            Stores the received keyword arguments in the surrounding `captured["send_kwargs"]` for assertions and returns a fake SQS response.
            
            Parameters:
                **kwargs (object): Keyword arguments that would be passed to an SQS client's send_message; stored for inspection.
            
            Returns:
                dict[str, str]: A fake response dictionary with `MessageId` set to `"1"`.
            """
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
            """
            Simulate an SQS send_message call that always raises a throttling ClientError.
            
            Ignores all keyword arguments and raises botocore.exceptions.ClientError with error response Error Code "ThrottlingException" and operation name "SendMessage".
            
            Raises:
                ClientError: Indicates a throttling error (Error Code "ThrottlingException") for the "SendMessage" operation.
            """
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
            """
            Simulate an SQS client's send_message by always raising a BotoCoreError.
            
            Raises:
                BotoCoreError: always raised to simulate a client-side failure when sending a message.
            """
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
    """
    Verifies that updating a RUNNING job to SUCCEEDED updates the result and clears any existing error.
    
    Creates a job in RUNNING state with a previous result and an error, calls update_result to set status to SUCCEEDED with a new result, and asserts the stored job has status SUCCEEDED, the result is replaced by the new value, and the error field is cleared.
    """
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
    """
    Verifies that cancelling a job returns the repository's concurrent terminal state instead of overwriting it.
    
    Sets up a repository that injects a concurrent SUCCEEDED state for the job; calling JobService.cancel must return the repository's terminal record (status SUCCEEDED and result {"accepted": True}) and must not increment the "jobs_canceled" metric.
    """
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
    """
    Verifies that cancelling a pending job raises a conflict error after retry attempts when the repository never applies status updates.
    
    Sets up a _NeverSettlingRepository containing a pending job, calls JobService.cancel for that job, and asserts a FileTransferError is raised with code "conflict" and HTTP status 409.
    """
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


def test_update_job_result_requires_valid_worker_token() -> None:
    """
    Verify that updating a job's result requires the correct worker token and records activity on success.
    
    Sends a POST to the internal job result update endpoint without and with the configured worker token. Asserts that a request with an incorrect token is rejected with a forbidden error and that a request with the valid token succeeds, updates the job status to `succeeded`, accepts the provided result payload, and produces activity events.
    """
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
    repository._records["job-update-3"] = JobRecord(
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
    assert cast(MemoryActivityStore, container.activity_store)._events_per_day


def test_get_job_status_failure_emits_error_observability(
    capture_emf: CaptureEmf,
) -> None:
    """
    Verifies that a failing job status request produces an error response, increments failure metrics, emits an error observability dimension for the route, and records activity events.
    
    This test:
    - Sends GET /v1/jobs/job-status-1 using a container whose job service fails.
    - Asserts the response status is 500.
    - Asserts the metrics counter "jobs_status_failure_total" is incremented.
    - Asserts an emitted EMF dimension includes {"route": "jobs_status", "status": "error"}.
    - Asserts that at least one activity event was recorded.
    
    Parameters:
        capture_emf (Callable[[MetricsCollector], list[dict]]): Test helper that captures EMF dimension dictionaries emitted by the provided metrics collector.
    """
    container, metrics, activity_store = _build_failing_job_container()
    emitted_dimensions = capture_emf(metrics)
    app = create_app(container_override=container)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/v1/jobs/job-status-1")

    assert response.status_code == 500
    counters = metrics.counters_snapshot()
    assert counters["jobs_status_failure_total"] == 1
    assert {"route": "jobs_status", "status": "error"} in emitted_dimensions
    assert activity_store._events_per_day


def test_legacy_cancel_route_is_not_exposed() -> None:
    """Verify legacy cancel route is not exposed and returns 404."""
    app = create_app(
        container_override=_build_same_origin_status_container(
            scope_id="scope-legacy"
        )
    )
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
    assert activity_store._events_per_day


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
    assert activity_store._events_per_day


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