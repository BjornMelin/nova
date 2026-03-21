from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from botocore.exceptions import ClientError
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.config import Settings
from nova_file_api.errors import (
    FileTransferError,
    invalid_request,
    not_found,
    service_unavailable,
    upstream_s3_error,
)
from nova_file_api.jobs import (
    JobService,
    MemoryJobPublisher,
    MemoryJobRepository,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    ActivityStoreBackend,
    JobRecord,
    JobsQueueBackend,
    JobsRepositoryBackend,
    JobStatus,
)
from nova_file_api.transfer import ExportCopyResult, TransferService
from nova_file_api.worker import (
    JobsWorker,
    _is_visibility_timeout_ceiling_error,
)


class _AsyncContext:
    """Wrap an object in an async context-manager interface."""

    def __init__(self, value: Any) -> None:
        self._value = value

    async def __aenter__(self) -> Any:
        return self._value

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> bool:
        del exc_type, exc, tb
        return False


class _FakeSession:
    """Expose aioboto3 Session.client API for worker run tests."""

    def __init__(
        self,
        *,
        sqs_client: Any,
        s3_client: Any,
        dynamodb_resource: Any | None = None,
    ) -> None:
        self._sqs_client = sqs_client
        self._s3_client = s3_client
        self._dynamodb_resource = (
            object() if dynamodb_resource is None else dynamodb_resource
        )

    def client(self, service_name: str, **kwargs: Any) -> _AsyncContext:
        del kwargs
        if service_name == "sqs":
            return _AsyncContext(self._sqs_client)
        if service_name == "s3":
            return _AsyncContext(self._s3_client)
        raise AssertionError(f"unexpected service name: {service_name}")

    def resource(self, service_name: str, **kwargs: Any) -> _AsyncContext:
        del kwargs
        if service_name == "dynamodb":
            return _AsyncContext(self._dynamodb_resource)
        raise AssertionError(f"unexpected resource name: {service_name}")


class _FakeSqsClient:
    """Capture SQS interactions for worker tests."""

    def __init__(self) -> None:
        self.receive_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self.change_visibility_calls: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []

    async def receive_message(self, **kwargs: Any) -> dict[str, Any]:
        self.receive_calls.append(kwargs)
        if not self.messages:
            return {"Messages": []}
        return {"Messages": list(self.messages)}

    async def delete_message(self, **kwargs: Any) -> None:
        self.delete_calls.append(kwargs)

    async def change_message_visibility(self, **kwargs: Any) -> None:
        self.change_visibility_calls.append(kwargs)


class _FakeTransferService:
    """Provide deterministic transfer worker outcomes."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result: ExportCopyResult | None = None
        self.error: Exception | None = None
        self.delay_seconds = 0.0

    async def copy_upload_to_export(
        self,
        *,
        source_bucket: str,
        source_key: str,
        scope_id: str,
        job_id: str,
        filename: str,
    ) -> ExportCopyResult:
        self.calls.append(
            {
                "source_bucket": source_bucket,
                "source_key": source_key,
                "scope_id": scope_id,
                "job_id": job_id,
                "filename": filename,
            }
        )
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return ExportCopyResult(
            export_key=f"exports/{scope_id}/{job_id}/{filename}",
            download_filename=filename,
        )


class _ScriptedJobService:
    """Replay a scripted sequence of result-update outcomes."""

    def __init__(
        self,
        *,
        fallback: JobService,
        scripted_results: list[FileTransferError | None],
    ) -> None:
        self._fallback = fallback
        self._scripted_results = scripted_results

    async def update_result(self, **kwargs: Any) -> JobRecord:
        if self._scripted_results:
            next_result = self._scripted_results.pop(0)
            if next_result is not None:
                raise next_result
        return await self._fallback.update_result(**kwargs)


class _FailingTerminalJobService:
    """Delegate running updates, then fail terminal updates repeatedly."""

    def __init__(self, *, fallback: JobService) -> None:
        self._fallback = fallback
        self.calls: list[JobStatus] = []

    async def update_result(self, **kwargs: Any) -> JobRecord:
        status = kwargs["status"]
        assert isinstance(status, JobStatus)
        self.calls.append(status)
        if status == JobStatus.RUNNING:
            return await self._fallback.update_result(**kwargs)
        raise RuntimeError("unexpected repository failure")


class _DeterministicSystemRandom:
    def uniform(self, _lower: float, _upper: float) -> float:
        return 1.0


def _worker_message_body(
    *,
    job_id: str = "job-1",
    job_type: str = "transfer.process",
    scope_id: str = "scope-1",
    payload: str | dict[str, Any] | None = None,
) -> str:
    parsed_payload = (
        {
            "bucket": "nova-bucket",
            "key": "uploads/scope-1/source.csv",
            "filename": "source.csv",
            "size_bytes": 42,
            "content_type": "text/csv",
        }
        if payload is None
        else (json.loads(payload) if isinstance(payload, str) else payload)
    )
    return json.dumps(
        {
            "job_id": job_id,
            "job_type": job_type,
            "scope_id": scope_id,
            "created_at": "2026-03-06T16:00:00Z",
            "payload": parsed_payload,
        }
    )


def _worker_settings() -> Settings:
    return Settings.model_validate(_worker_settings_env())


def _worker_settings_env(**overrides: object) -> dict[str, object]:
    """Return a valid worker settings payload."""
    env: dict[str, object] = {
        "JOBS_ENABLED": True,
        "JOBS_RUNTIME_MODE": "worker",
        "JOBS_QUEUE_BACKEND": JobsQueueBackend.SQS,
        "JOBS_SQS_QUEUE_URL": "https://example.local/queue",
        "JOBS_REPOSITORY_BACKEND": JobsRepositoryBackend.DYNAMODB,
        "JOBS_DYNAMODB_TABLE": "jobs-table",
        "ACTIVITY_STORE_BACKEND": ActivityStoreBackend.DYNAMODB,
        "ACTIVITY_ROLLUPS_TABLE": "activity-table",
    }
    env.update(overrides)
    return env


async def _build_worker_runtime(
    *,
    job_id: str = "job-1",
    scope_id: str = "scope-1",
    status: JobStatus = JobStatus.PENDING,
) -> tuple[MemoryJobRepository, JobService, MemoryActivityStore]:
    repository = MemoryJobRepository()
    service = JobService(
        repository=repository,
        publisher=MemoryJobPublisher(),
        metrics=MetricsCollector(namespace="Tests"),
    )
    activity_store = MemoryActivityStore()
    now = datetime.now(tz=UTC)
    await repository.create(
        JobRecord(
            job_id=job_id,
            job_type="transfer.process",
            scope_id=scope_id,
            status=status,
            payload={"input": "value"},
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
        )
    )
    return repository, service, activity_store


def _attach_runtime_clients(
    *,
    worker: JobsWorker,
    sqs_client: _FakeSqsClient,
    transfer_service: _FakeTransferService,
    job_service: JobService,
    activity_store: MemoryActivityStore,
) -> None:
    worker._sqs = sqs_client
    worker._runtime_transfer_service = cast(TransferService, transfer_service)
    worker._runtime_job_service = job_service
    worker._runtime_activity_store = activity_store


def _build_worker(
    *,
    settings: Settings | None = None,
    transfer_service: _FakeTransferService | None = None,
) -> JobsWorker:
    concrete_transfer_service = (
        _FakeTransferService() if transfer_service is None else transfer_service
    )
    return JobsWorker(
        settings=_worker_settings() if settings is None else settings,
        transfer_service=cast(TransferService, concrete_transfer_service),
    )


@pytest.mark.asyncio
async def test_worker_receive_sqs_settings() -> None:
    """Verify worker receive-message call uses configured SQS settings."""
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    settings = Settings.model_validate(
        _worker_settings_env(
            JOBS_SQS_QUEUE_URL=(
                "https://sqs.us-west-2.amazonaws.com/123456789012/nova-jobs"
            ),
            JOBS_SQS_MAX_NUMBER_OF_MESSAGES=5,
            JOBS_SQS_WAIT_TIME_SECONDS=7,
            JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS=180,
        )
    )
    worker = _build_worker(
        settings=settings,
        transfer_service=transfer_service,
    )
    worker._sqs = fake_sqs

    assert await worker._receive_messages() == []
    queue_url = "https://sqs.us-west-2.amazonaws.com/123456789012/nova-jobs"
    assert fake_sqs.receive_calls == [
        {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": 5,
            "WaitTimeSeconds": 7,
            "VisibilityTimeout": 180,
            "MessageSystemAttributeNames": ["ApproximateReceiveCount"],
        }
    ]


@pytest.mark.asyncio
async def test_worker_invalid_message_is_not_deleted() -> None:
    """Verify that malformed or invalid SQS messages are not acked/deleted."""
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    _, job_service, activity_store = await _build_worker_runtime()
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        transfer_service=transfer_service,
        job_service=job_service,
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-1",
            "ReceiptHandle": "receipt-1",
            "Body": '{"invalid":true}',
            "Attributes": {"ApproximateReceiveCount": "3"},
        }
    )

    assert should_delete is False
    assert fake_sqs.delete_calls == []


@pytest.mark.asyncio
async def test_worker_posts_failed_status_for_unsupported_job_type() -> None:
    """Verify worker reports failure when encountering an unknown job type."""
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    repository, job_service, activity_store = await _build_worker_runtime()
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        transfer_service=transfer_service,
        job_service=job_service,
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-2",
            "ReceiptHandle": "receipt-2",
            "Body": _worker_message_body(job_type="unknown.job"),
            "Attributes": {"ApproximateReceiveCount": "1"},
        }
    )

    assert should_delete is True
    record = await repository.get("job-1")
    assert record is not None
    assert record.status == JobStatus.FAILED
    assert record.error == "unsupported job type: unknown.job"


@pytest.mark.asyncio
async def test_worker_executes_transfer_process_and_posts_success() -> None:
    """Verify successful end-to-end transfer job processing and reporting."""
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    repository, job_service, activity_store = await _build_worker_runtime(
        job_id="job-2"
    )
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        transfer_service=transfer_service,
        job_service=job_service,
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-3",
            "ReceiptHandle": "receipt-3",
            "Body": _worker_message_body(job_id="job-2"),
            "Attributes": {"ApproximateReceiveCount": "2"},
        }
    )

    assert should_delete is True
    assert transfer_service.calls == [
        {
            "source_bucket": "nova-bucket",
            "source_key": "uploads/scope-1/source.csv",
            "scope_id": "scope-1",
            "job_id": "job-2",
            "filename": "source.csv",
        }
    ]
    record = await repository.get("job-2")
    assert record is not None
    assert record.status == JobStatus.SUCCEEDED
    assert record.result == {
        "export_key": "exports/scope-1/job-2/source.csv",
        "download_filename": "source.csv",
    }
    assert record.error is None
    activity_summary = await activity_store.summary()
    assert activity_summary["events_total"] == 2


@pytest.mark.asyncio
async def test_worker_extends_visibility_during_long_running_transfer() -> None:
    """Verify long-running transfer work refreshes SQS visibility timeout."""
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    transfer_service.delay_seconds = 1.2
    _, job_service, activity_store = await _build_worker_runtime(job_id="job-2")
    settings = Settings.model_validate(
        _worker_settings_env(
            JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS=1,
        )
    )
    worker = _build_worker(
        settings=settings,
        transfer_service=transfer_service,
    )
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        transfer_service=transfer_service,
        job_service=job_service,
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-3b",
            "ReceiptHandle": "receipt-3b",
            "Body": _worker_message_body(job_id="job-2"),
            "Attributes": {"ApproximateReceiveCount": "2"},
        }
    )

    assert should_delete is True
    assert len(fake_sqs.change_visibility_calls) >= 1
    assert all(
        call
        == {
            "QueueUrl": "https://example.local/queue",
            "ReceiptHandle": "receipt-3b",
            "VisibilityTimeout": 1,
        }
        for call in fake_sqs.change_visibility_calls
    )


@pytest.mark.asyncio
async def test_worker_non_retryable_error_posts_failure() -> None:
    """Verify worker reports failure for non-retryable execution errors."""
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    transfer_service.error = invalid_request("source upload object not found")
    repository, job_service, activity_store = await _build_worker_runtime(
        job_id="job-2"
    )
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        transfer_service=transfer_service,
        job_service=job_service,
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-4",
            "ReceiptHandle": "receipt-4",
            "Body": _worker_message_body(job_id="job-2"),
            "Attributes": {"ApproximateReceiveCount": "2"},
        }
    )

    assert should_delete is True
    record = await repository.get("job-2")
    assert record is not None
    assert record.status == JobStatus.FAILED
    assert record.error == "source upload object not found"


def test_visibility_timeout_ceiling_error_detector() -> None:
    """SQS 12-hour ceiling responses must be detected as non-retryable."""
    exc = ClientError(
        error_response={
            "Error": {
                "Code": "InvalidParameterValue",
                "Message": (
                    "Value 43200 for parameter VisibilityTimeout exceeds "
                    "the maximum visibility timeout"
                ),
            }
        },
        operation_name="ChangeMessageVisibility",
    )
    assert _is_visibility_timeout_ceiling_error(exc) is True

    other_exc = ClientError(
        error_response={
            "Error": {
                "Code": "AccessDenied",
                "Message": "not authorized",
            }
        },
        operation_name="ChangeMessageVisibility",
    )
    assert _is_visibility_timeout_ceiling_error(other_exc) is False


@pytest.mark.asyncio
async def test_worker_retryable_error_leaves_message_unacked() -> None:
    """Verify worker leaves message unacked for retryable execution errors."""
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    transfer_service.error = upstream_s3_error(
        "failed to copy upload object to export key"
    )
    repository, job_service, activity_store = await _build_worker_runtime(
        job_id="job-2"
    )
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        transfer_service=transfer_service,
        job_service=job_service,
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-5",
            "ReceiptHandle": "receipt-5",
            "Body": _worker_message_body(job_id="job-2"),
            "Attributes": {"ApproximateReceiveCount": "2"},
        }
    )

    assert should_delete is False
    assert fake_sqs.delete_calls == []
    record = await repository.get("job-2")
    assert record is not None
    assert record.status == JobStatus.RUNNING


@pytest.mark.asyncio
async def test_worker_acks_terminal_redelivery_without_processing() -> None:
    """Verify terminal job redeliveries do not become poison messages."""
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    repository, job_service, activity_store = await _build_worker_runtime(
        job_id="job-2",
        status=JobStatus.SUCCEEDED,
    )
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        transfer_service=transfer_service,
        job_service=job_service,
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-terminal",
            "ReceiptHandle": "receipt-terminal",
            "Body": _worker_message_body(job_id="job-2"),
            "Attributes": {"ApproximateReceiveCount": "4"},
        }
    )

    assert should_delete is True
    assert transfer_service.calls == []
    record = await repository.get("job-2")
    assert record is not None
    assert record.status == JobStatus.SUCCEEDED
    assert record.error is None


@pytest.mark.asyncio
async def test_worker_records_generic_result_update_failure() -> None:
    """Verify unexpected result-update failures are recorded and retried."""
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    transfer_service.result = ExportCopyResult(
        export_key="exports/scope-1/job-2/source.csv",
        download_filename="source.csv",
    )
    repository, job_service, activity_store = await _build_worker_runtime(
        job_id="job-2"
    )
    failing_job_service = _FailingTerminalJobService(fallback=job_service)
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        transfer_service=transfer_service,
        job_service=cast(JobService, failing_job_service),
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-generic",
            "ReceiptHandle": "receipt-generic",
            "Body": _worker_message_body(job_id="job-2"),
            "Attributes": {"ApproximateReceiveCount": "2"},
        }
    )

    assert should_delete is False
    assert failing_job_service.calls == [
        JobStatus.RUNNING,
        JobStatus.SUCCEEDED,
        JobStatus.SUCCEEDED,
        JobStatus.SUCCEEDED,
    ]
    record = await repository.get("job-2")
    assert record is not None
    assert record.status == JobStatus.RUNNING
    activity_summary = await activity_store.summary()
    assert activity_summary["events_total"] == 4


@pytest.mark.asyncio
async def test_worker_retries_running_update_until_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify worker retries the initial 'running' status post until success.

    Args:
        monkeypatch: Pytest fixture for mocking asyncio sleep and random.

    Returns:
        None
    """
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    repository, job_service, activity_store = await _build_worker_runtime(
        job_id="job-2"
    )
    sleep_calls: list[float] = []
    flaky_job_service = _ScriptedJobService(
        fallback=job_service,
        scripted_results=[
            not_found("job not found"),
            service_unavailable("storage temporarily unavailable"),
        ],
    )

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("nova_file_api.worker.asyncio.sleep", _fake_sleep)

    monkeypatch.setattr(
        "nova_file_api.worker.secrets.SystemRandom",
        _DeterministicSystemRandom,
    )

    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        transfer_service=transfer_service,
        job_service=cast(JobService, flaky_job_service),
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-6",
            "ReceiptHandle": "receipt-6",
            "Body": _worker_message_body(job_id="job-2"),
            "Attributes": {"ApproximateReceiveCount": "1"},
        }
    )

    assert should_delete is True
    assert sleep_calls == [0.25, 0.5]
    assert len(transfer_service.calls) == 1
    record = await repository.get("job-2")
    assert record is not None
    assert record.status == JobStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_worker_unacked_when_terminal_update_retries_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify message remains unacked if terminal result post fails repeatedly.

    Args:
        monkeypatch: Pytest fixture for mocking asyncio sleep and random.

    Returns:
        None
    """
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    repository, job_service, activity_store = await _build_worker_runtime(
        job_id="job-2"
    )
    flaky_job_service = _ScriptedJobService(
        fallback=job_service,
        scripted_results=[
            None,
            service_unavailable("storage temporarily unavailable"),
            service_unavailable("storage temporarily unavailable"),
            service_unavailable("storage temporarily unavailable"),
        ],
    )

    async def _fake_sleep(delay: float) -> None:
        del delay
        return None

    monkeypatch.setattr("nova_file_api.worker.asyncio.sleep", _fake_sleep)

    monkeypatch.setattr(
        "nova_file_api.worker.secrets.SystemRandom",
        _DeterministicSystemRandom,
    )

    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        transfer_service=transfer_service,
        job_service=cast(JobService, flaky_job_service),
        activity_store=activity_store,
    )

    should_delete = await worker._handle_message(
        message={
            "MessageId": "msg-7",
            "ReceiptHandle": "receipt-7",
            "Body": _worker_message_body(job_id="job-2"),
            "Attributes": {"ApproximateReceiveCount": "1"},
        }
    )

    assert should_delete is False
    record = await repository.get("job-2")
    assert record is not None
    assert record.status == JobStatus.RUNNING


@pytest.mark.asyncio
async def test_worker_run_deletes_message_when_non_retryable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify end-to-end worker.run() deletes message on non-retryable error.

    Args:
        monkeypatch: Pytest fixture for mocking runtime service construction.

    Returns:
        None
    """
    captured_transfer_service_args: (
        tuple[tuple[Any, ...], dict[str, Any]] | None
    ) = None
    fake_sqs = _FakeSqsClient()
    fake_s3_client = object()
    transfer_service = _FakeTransferService()
    transfer_service.error = invalid_request("source upload object not found")
    settings = _worker_settings()
    repository, job_service, activity_store = await _build_worker_runtime(
        job_id="job-2"
    )

    worker = JobsWorker(
        settings=settings,
        transfer_service=None,
        job_service=job_service,
        activity_store=activity_store,
    )
    worker._session = cast(
        Any,
        _FakeSession(
            sqs_client=fake_sqs,
            s3_client=fake_s3_client,
        ),
    )

    async def _receive_once() -> list[dict[str, Any]]:
        worker._stop_requested = True
        return [
            {
                "MessageId": "msg-8",
                "ReceiptHandle": "receipt-8",
                "Body": _worker_message_body(job_id="job-2"),
                "Attributes": {"ApproximateReceiveCount": "2"},
            }
        ]

    monkeypatch.setattr(worker, "_receive_messages", _receive_once)
    monkeypatch.setattr(worker, "_install_signal_handlers", lambda: None)

    def _capture_transfer_service(
        *args: Any,
        **kwargs: Any,
    ) -> _FakeTransferService:
        nonlocal captured_transfer_service_args
        captured_transfer_service_args = (args, kwargs)
        return transfer_service

    monkeypatch.setattr(
        "nova_file_api.worker.TransferService",
        _capture_transfer_service,
    )

    exit_code = await worker.run()

    assert exit_code == 0
    assert captured_transfer_service_args is not None
    (
        transfer_service_args,
        transfer_service_kwargs,
    ) = captured_transfer_service_args
    assert transfer_service_args == ()
    assert transfer_service_kwargs["settings"] is settings
    assert transfer_service_kwargs["s3_client"] is fake_s3_client
    assert fake_sqs.delete_calls == [
        {
            "QueueUrl": "https://example.local/queue",
            "ReceiptHandle": "receipt-8",
        }
    ]
    record = await repository.get("job-2")
    assert record is not None
    assert record.status == JobStatus.FAILED
