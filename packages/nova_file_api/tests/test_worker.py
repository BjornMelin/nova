from __future__ import annotations

import json
from typing import Any, cast

import httpx
import pytest
from nova_file_api.config import Settings
from nova_file_api.errors import invalid_request, upstream_s3_error
from nova_file_api.models import JobsQueueBackend
from nova_file_api.transfer import ExportCopyResult, TransferService
from nova_file_api.worker import JobsWorker
from pydantic import SecretStr


class _AsyncContext:
    """Wrap an object in an async context-manager interface."""

    def __init__(self, value: Any) -> None:
        """
        Initialize the async context wrapper with a stored value.
        
        Parameters:
            value (Any): The object that will be returned by __aenter__ when the context is entered.
        """
        self._value = value

    async def __aenter__(self) -> Any:
        """
        Provide the wrapped value when entering the asynchronous context manager.
        
        Returns:
            The stored value held by the context manager.
        """
        return self._value

    async def __aexit__(
        self, exc_type: object, exc: object, tb: object
    ) -> bool:
        """
        Exit the asynchronous context manager without suppressing exceptions.
        
        Returns:
            False: indicates any exception raised inside the context should be propagated.
        """
        del exc_type, exc, tb
        return False


class _FakeSession:
    """Expose aioboto3 Session.client API for worker run tests."""

    def __init__(self, *, sqs_client: Any, s3_client: Any) -> None:
        """
        Initialize the fake session with the provided SQS and S3 client objects.
        
        Parameters:
            sqs_client (Any): An object that implements the asynchronous SQS client interface used in tests (e.g., async receive_message and delete_message).
            s3_client (Any): An object that implements the S3 client interface used in tests.
        """
        self._sqs_client = sqs_client
        self._s3_client = s3_client

    def client(self, service_name: str, **kwargs: Any) -> _AsyncContext:
        """
        Return an async context manager that yields a fake runtime client for the given service.
        
        Parameters:
            service_name (str): Name of the service to retrieve; must be either "sqs" or "s3". Any additional keyword arguments are ignored.
        
        Returns:
            _AsyncContext: An async context manager that yields the corresponding fake client.
        
        Raises:
            AssertionError: If service_name is not "sqs" or "s3".
        """
        del kwargs
        if service_name == "sqs":
            return _AsyncContext(self._sqs_client)
        if service_name == "s3":
            return _AsyncContext(self._s3_client)
        raise AssertionError(f"unexpected service name: {service_name}")


class _FakeSqsClient:
    """Capture SQS interactions for worker tests."""

    def __init__(self) -> None:
        """
        Initialize the fake SQS client capturing calls and queued messages for tests.
        
        Attributes:
            receive_calls (list[dict[str, Any]]): Recorded kwargs for each receive_message invocation.
            delete_calls (list[dict[str, Any]]): Recorded kwargs for each delete_message invocation.
            messages (list[dict[str, Any]]): Preloaded messages to be returned by receive_message.
        """
        self.receive_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []

    async def receive_message(self, **kwargs: Any) -> dict[str, Any]:
        """
        Simulates receiving messages from an SQS-like queue for tests and records the call arguments.
        
        Parameters:
            **kwargs: Additional parameters passed to the simulated receive_message call; these are recorded in self.receive_calls.
        
        Returns:
            dict: A mapping with key "Messages" whose value is a list of message dicts from self.messages; returns an empty list when no messages are available.
        """
        self.receive_calls.append(kwargs)
        if not self.messages:
            return {"Messages": []}
        return {"Messages": list(self.messages)}

    async def delete_message(self, **kwargs: Any) -> None:
        """
        Record parameters of an SQS `delete_message` invocation for test inspection.
        
        Appends the provided keyword arguments to `self.delete_calls` so tests can assert which
        delete requests would have been made (e.g., QueueUrl and ReceiptHandle).
        """
        self.delete_calls.append(kwargs)


class _FakeHttpClient:
    """Capture internal result callback POST requests."""

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize the fake HTTP client with optional configuration.
        
        Parameters:
            **kwargs: Arbitrary configuration values provided for test setup; stored on the instance as `kwargs` but not otherwise used.
        
        Attributes:
            kwargs (dict): The provided configuration kwargs.
            responses (list[httpx.Response | Exception]): Queue of responses or exceptions that post() will return or raise.
            posts (list[dict[str, Any]]): Recorded POST requests, each as a dict with keys like "url" and "json".
        """
        self.kwargs = kwargs
        self.responses: list[httpx.Response | Exception] = []
        self.posts: list[dict[str, Any]] = []

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """
        Simulate an HTTP POST by recording the request and returning or raising the next queued response.
        
        Parameters:
            url (str): The destination URL of the POST.
            **kwargs: Expect a `json` keyword containing the JSON payload that will be recorded.
        
        Returns:
            httpx.Response: The next response object popped from the internal responses queue.
        
        Raises:
            Exception: If the next item in the internal responses queue is an Exception, that exception is raised.
        """
        self.posts.append({"url": url, "json": kwargs["json"]})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeTransferService:
    """Provide deterministic transfer worker outcomes."""

    def __init__(self) -> None:
        """
        Initialize a deterministic fake transfer service for tests.
        
        Attributes:
            calls (list[dict[str, Any]]): Recorded arguments for each `copy_upload_to_export` invocation.
            result (ExportCopyResult | None): Predefined result to return from `copy_upload_to_export` when set.
            error (Exception | None): Predefined exception to raise from `copy_upload_to_export` when set.
        """
        self.calls: list[dict[str, Any]] = []
        self.result: ExportCopyResult | None = None
        self.error: Exception | None = None

    async def copy_upload_to_export(
        self,
        *,
        source_bucket: str,
        source_key: str,
        scope_id: str,
        job_id: str,
        filename: str,
    ) -> ExportCopyResult:
        """
        Copy an upload object into an export location and return the export metadata.
        
        Returns:
            ExportCopyResult: Object containing `export_key` (S3 key for the export) and `download_filename` (filename clients should use).
        
        Raises:
            Exception: If the transfer service has been configured with an error, that exception is raised.
        """
        self.calls.append(
            {
                "source_bucket": source_bucket,
                "source_key": source_key,
                "scope_id": scope_id,
                "job_id": job_id,
                "filename": filename,
            }
        )
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return ExportCopyResult(
            export_key=f"exports/{scope_id}/{job_id}/{filename}",
            download_filename=filename,
        )


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
    """
    Create a Settings instance preconfigured for a worker process.
    
    The returned Settings has worker-specific values required for tests:
    - JOBS_ENABLED: True
    - JOBS_RUNTIME_MODE: "worker"
    - JOBS_QUEUE_BACKEND: SQS
    - JOBS_SQS_QUEUE_URL: "https://example.local/queue"
    - JOBS_API_BASE_URL: "https://api.example.local"
    - JOBS_WORKER_UPDATE_TOKEN: SecretStr("worker-token")
    
    Returns:
        Settings: A Settings object populated with the above worker configuration.
    """
    return Settings.model_validate(
        {
            "JOBS_ENABLED": True,
            "JOBS_RUNTIME_MODE": "worker",
            "JOBS_QUEUE_BACKEND": JobsQueueBackend.SQS,
            "JOBS_SQS_QUEUE_URL": "https://example.local/queue",
            "JOBS_API_BASE_URL": "https://api.example.local",
            "JOBS_WORKER_UPDATE_TOKEN": SecretStr("worker-token"),
        }
    )


def _attach_runtime_clients(
    *,
    worker: JobsWorker,
    sqs_client: _FakeSqsClient,
    api_client: _FakeHttpClient,
    transfer_service: _FakeTransferService,
) -> None:
    """
    Injects test runtime clients into a JobsWorker instance by assigning the provided fake clients and transfer service to the worker's internal attributes.
    
    Parameters:
        worker (JobsWorker): Worker instance to modify.
        sqs_client (_FakeSqsClient): Fake SQS client to assign to worker._sqs.
        api_client (_FakeHttpClient): Fake HTTP client to assign to worker._api (cast to httpx.AsyncClient).
        transfer_service (_FakeTransferService): Fake transfer service to assign to worker._runtime_transfer_service (cast to TransferService).
    """
    worker._sqs = sqs_client
    worker._api = cast(httpx.AsyncClient, api_client)
    worker._runtime_transfer_service = cast(TransferService, transfer_service)


def _build_worker(
    *,
    settings: Settings | None = None,
    transfer_service: _FakeTransferService | None = None,
) -> JobsWorker:
    """
    Constructs a JobsWorker configured for tests.
    
    Parameters:
        settings (Settings | None): Optional Settings to use for the worker; when omitted, a test Settings instance is created.
        transfer_service (_FakeTransferService | None): Optional fake TransferService to use; when omitted, a new _FakeTransferService is created.
    
    Returns:
        JobsWorker: A JobsWorker initialized with the provided or default Settings and a deterministic transfer service suitable for testing.
    """
    concrete_transfer_service = (
        _FakeTransferService() if transfer_service is None else transfer_service
    )
    return JobsWorker(
        settings=_worker_settings() if settings is None else settings,
        transfer_service=cast(TransferService, concrete_transfer_service),
    )


@pytest.mark.asyncio
async def test_worker_receive_message_uses_configured_sqs_settings() -> None:
    fake_sqs = _FakeSqsClient()
    transfer_service = _FakeTransferService()
    settings = Settings.model_validate(
        {
            "JOBS_ENABLED": True,
            "JOBS_RUNTIME_MODE": "worker",
            "JOBS_QUEUE_BACKEND": JobsQueueBackend.SQS,
            "JOBS_SQS_QUEUE_URL": (
                "https://sqs.us-west-2.amazonaws.com/123456789012/nova-jobs"
            ),
            "JOBS_API_BASE_URL": "https://api.example.local",
            "JOBS_WORKER_UPDATE_TOKEN": SecretStr("worker-token"),
            "JOBS_SQS_MAX_NUMBER_OF_MESSAGES": 5,
            "JOBS_SQS_WAIT_TIME_SECONDS": 7,
            "JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS": 180,
        }
    )
    worker = _build_worker(
        settings=settings,
        transfer_service=transfer_service,
    )
    worker._sqs = fake_sqs

    assert await worker._receive_messages() == []
    assert fake_sqs.receive_calls == [
        {
            "QueueUrl": "https://sqs.us-west-2.amazonaws.com/123456789012/nova-jobs",
            "MaxNumberOfMessages": 5,
            "WaitTimeSeconds": 7,
            "VisibilityTimeout": 180,
            "MessageSystemAttributeNames": ["ApproximateReceiveCount"],
        }
    ]


@pytest.mark.asyncio
async def test_worker_invalid_message_is_not_deleted() -> None:
    fake_sqs = _FakeSqsClient()
    fake_http = _FakeHttpClient()
    transfer_service = _FakeTransferService()
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        api_client=fake_http,
        transfer_service=transfer_service,
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
    assert fake_http.posts == []
    assert fake_sqs.delete_calls == []


@pytest.mark.asyncio
async def test_worker_posts_failed_status_for_unsupported_job_type() -> None:
    fake_sqs = _FakeSqsClient()
    fake_http = _FakeHttpClient()
    fake_http.responses.append(
        httpx.Response(
            200,
            request=httpx.Request(
                "POST",
                "https://api.example.local/v1/internal/jobs/job-1/result",
            ),
        )
    )
    transfer_service = _FakeTransferService()
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        api_client=fake_http,
        transfer_service=transfer_service,
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
    assert fake_http.posts == [
        {
            "url": "/v1/internal/jobs/job-1/result",
            "json": {
                "status": "failed",
                "result": None,
                "error": "unsupported job type: unknown.job",
            },
        }
    ]


@pytest.mark.asyncio
async def test_worker_executes_transfer_process_and_posts_success() -> None:
    fake_sqs = _FakeSqsClient()
    fake_http = _FakeHttpClient()
    fake_http.responses.extend(
        [
            httpx.Response(
                200,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
            httpx.Response(
                200,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
        ]
    )
    transfer_service = _FakeTransferService()
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        api_client=fake_http,
        transfer_service=transfer_service,
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
    assert fake_http.posts == [
        {
            "url": "/v1/internal/jobs/job-2/result",
            "json": {
                "status": "running",
                "result": None,
                "error": None,
            },
        },
        {
            "url": "/v1/internal/jobs/job-2/result",
            "json": {
                "status": "succeeded",
                "result": {
                    "export_key": "exports/scope-1/job-2/source.csv",
                    "download_filename": "source.csv",
                },
                "error": None,
            },
        },
    ]


@pytest.mark.asyncio
async def test_worker_non_retryable_execution_failure_posts_failure() -> None:
    fake_sqs = _FakeSqsClient()
    fake_http = _FakeHttpClient()
    fake_http.responses.extend(
        [
            httpx.Response(
                200,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
            httpx.Response(
                200,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
        ]
    )
    transfer_service = _FakeTransferService()
    transfer_service.error = invalid_request("source upload object not found")
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        api_client=fake_http,
        transfer_service=transfer_service,
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
    assert fake_http.posts == [
        {
            "url": "/v1/internal/jobs/job-2/result",
            "json": {
                "status": "running",
                "result": None,
                "error": None,
            },
        },
        {
            "url": "/v1/internal/jobs/job-2/result",
            "json": {
                "status": "failed",
                "result": None,
                "error": "source upload object not found",
            },
        },
    ]


@pytest.mark.asyncio
async def test_worker_retryable_execution_failure_leaves_message_unacked() -> (
    None
):
    fake_sqs = _FakeSqsClient()
    fake_http = _FakeHttpClient()
    fake_http.responses.append(
        httpx.Response(
            200,
            request=httpx.Request(
                "POST",
                "https://api.example.local/v1/internal/jobs/job-2/result",
            ),
        )
    )
    transfer_service = _FakeTransferService()
    transfer_service.error = upstream_s3_error(
        "failed to copy upload object to export key"
    )
    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        api_client=fake_http,
        transfer_service=transfer_service,
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
    assert fake_http.posts == [
        {
            "url": "/v1/internal/jobs/job-2/result",
            "json": {
                "status": "running",
                "result": None,
                "error": None,
            },
        }
    ]


@pytest.mark.asyncio
async def test_worker_retries_running_update_until_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_sqs = _FakeSqsClient()
    fake_http = _FakeHttpClient()
    fake_http.responses.extend(
        [
            httpx.Response(
                404,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
            httpx.Response(
                503,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
            httpx.Response(
                200,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
            httpx.Response(
                200,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
        ]
    )
    transfer_service = _FakeTransferService()
    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        """
        Record a simulated sleep delay into the shared sleep_calls list without pausing execution.
        
        Appends the provided delay value to the module-level `sleep_calls` list so tests can assert intended sleep durations instead of actually sleeping.
        
        Parameters:
            delay (float): The number of seconds that would have been slept.
        """
        sleep_calls.append(delay)

    monkeypatch.setattr("nova_file_api.worker.asyncio.sleep", _fake_sleep)
    monkeypatch.setattr(
        "nova_file_api.worker.random.uniform",
        lambda _lower, _upper: 1.0,
    )

    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        api_client=fake_http,
        transfer_service=transfer_service,
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
    assert len(fake_http.posts) == 4
    assert len(transfer_service.calls) == 1


@pytest.mark.asyncio
async def test_worker_unacked_when_terminal_update_retries_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_sqs = _FakeSqsClient()
    fake_http = _FakeHttpClient()
    fake_http.responses.extend(
        [
            httpx.Response(
                200,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
            httpx.Response(
                503,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
            httpx.Response(
                503,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
            httpx.Response(
                503,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
        ]
    )
    transfer_service = _FakeTransferService()

    async def _fake_sleep(delay: float) -> None:
        """
        No-op replacement for asyncio.sleep that immediately returns.
        
        Parameters:
            delay (float): Number of seconds to sleep (ignored).
        """
        del delay
        return None

    monkeypatch.setattr("nova_file_api.worker.asyncio.sleep", _fake_sleep)
    monkeypatch.setattr(
        "nova_file_api.worker.random.uniform",
        lambda _lower, _upper: 1.0,
    )

    worker = _build_worker(transfer_service=transfer_service)
    _attach_runtime_clients(
        worker=worker,
        sqs_client=fake_sqs,
        api_client=fake_http,
        transfer_service=transfer_service,
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
    assert len(fake_http.posts) == 4
    assert fake_http.posts[0]["json"] == {
        "status": "running",
        "result": None,
        "error": None,
    }


@pytest.mark.asyncio
async def test_worker_run_deletes_message_when_non_retryable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_sqs = _FakeSqsClient()
    fake_http = _FakeHttpClient()
    fake_http.responses.extend(
        [
            httpx.Response(
                200,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
            httpx.Response(
                200,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
        ]
    )
    transfer_service = _FakeTransferService()
    transfer_service.error = invalid_request("source upload object not found")

    worker = _build_worker(transfer_service=transfer_service)
    worker._session = cast(
        Any,
        _FakeSession(
            sqs_client=fake_sqs,
            s3_client=object(),
        ),
    )

    async def _receive_once() -> list[dict[str, Any]]:
        """
        Set the worker's stop flag and return a single mocked SQS-style message.
        
        This helper marks worker._stop_requested = True to signal the worker loop should stop, and returns a list containing one message dict with keys "MessageId", "ReceiptHandle", "Body" (a serialized worker message), and "Attributes" (including "ApproximateReceiveCount").
        
        Returns:
            list[dict[str, Any]]: A list with one SQS-like message dictionary.
        """
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
    monkeypatch.setattr(
        "nova_file_api.worker.httpx.AsyncClient",
        lambda **kwargs: _AsyncContext(fake_http),
    )
    monkeypatch.setattr(
        "nova_file_api.worker.TransferService",
        lambda settings, s3_client: transfer_service,
    )

    exit_code = await worker.run()

    assert exit_code == 0
    assert fake_sqs.delete_calls == [
        {
            "QueueUrl": "https://example.local/queue",
            "ReceiptHandle": "receipt-8",
        }
    ]
