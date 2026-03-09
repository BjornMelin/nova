from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from nova_file_api.config import Settings
from nova_file_api.errors import upstream_s3_error
from nova_file_api.models import JobsQueueBackend
from nova_file_api.transfer import ExportCopyResult
from nova_file_api.worker import JobsWorker
from pydantic import SecretStr


class _FakeSqsClient:
    def __init__(self) -> None:
        self.receive_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []

    def receive_message(self, **kwargs: Any) -> dict[str, Any]:
        self.receive_calls.append(kwargs)
        return {"Messages": []}

    def delete_message(self, **kwargs: Any) -> None:
        self.delete_calls.append(kwargs)


class _FakeHttpClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.responses: list[httpx.Response | Exception] = []
        self.posts: list[dict[str, Any]] = []

    def close(self) -> None:
        return None

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        json_data = kwargs["json"]
        self.posts.append({"url": url, "json": json_data})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeTransferService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._result: ExportCopyResult | None = None
        self._error: Exception | None = None

    def copy_upload_to_export(
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
        if self._error is not None:
            raise self._error
        if self._result is not None:
            return self._result
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


def test_worker_receive_message_uses_configured_sqs_polling_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_sqs = _FakeSqsClient()
    captured_client_kwargs: dict[str, Any] = {}

    def _fake_boto3_client(service_name: str, **kwargs: Any) -> _FakeSqsClient:
        assert service_name == "sqs"
        assert "config" in kwargs
        return fake_sqs

    def _fake_http_client(**kwargs: Any) -> _FakeHttpClient:
        captured_client_kwargs.update(kwargs)
        return _FakeHttpClient(**kwargs)

    monkeypatch.setattr("nova_file_api.worker.boto3.client", _fake_boto3_client)
    monkeypatch.setattr("nova_file_api.worker.httpx.Client", _fake_http_client)

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

    worker = JobsWorker(
        settings=settings,
        transfer_service=_FakeTransferService(),  # type: ignore[arg-type]
    )

    assert worker._receive_messages() == []
    assert fake_sqs.receive_calls == [
        {
            "QueueUrl": "https://sqs.us-west-2.amazonaws.com/123456789012/nova-jobs",
            "MaxNumberOfMessages": 5,
            "WaitTimeSeconds": 7,
            "VisibilityTimeout": 180,
            "MessageSystemAttributeNames": ["ApproximateReceiveCount"],
        }
    ]
    assert captured_client_kwargs["base_url"] == "https://api.example.local"
    assert captured_client_kwargs["headers"]["X-Worker-Token"] == "worker-token"


def test_worker_invalid_message_is_not_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_sqs = _FakeSqsClient()
    fake_http = _FakeHttpClient()

    monkeypatch.setattr(
        "nova_file_api.worker.boto3.client",
        lambda service_name, **kwargs: fake_sqs,
    )
    monkeypatch.setattr(
        "nova_file_api.worker.httpx.Client",
        lambda **kwargs: fake_http,
    )

    settings = Settings.model_validate(
        {
            "JOBS_ENABLED": True,
            "JOBS_RUNTIME_MODE": "worker",
            "JOBS_QUEUE_BACKEND": JobsQueueBackend.SQS,
            "JOBS_SQS_QUEUE_URL": "https://example.local/queue",
            "JOBS_API_BASE_URL": "https://api.example.local",
            "JOBS_WORKER_UPDATE_TOKEN": SecretStr("worker-token"),
        }
    )

    worker = JobsWorker(
        settings=settings,
        transfer_service=_FakeTransferService(),  # type: ignore[arg-type]
    )
    should_delete = worker._handle_message(
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


def test_worker_posts_failed_status_for_unsupported_job_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    monkeypatch.setattr(
        "nova_file_api.worker.boto3.client",
        lambda service_name, **kwargs: fake_sqs,
    )
    monkeypatch.setattr(
        "nova_file_api.worker.httpx.Client",
        lambda **kwargs: fake_http,
    )

    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_runtime_mode = "worker"
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = "https://example.local/queue"
    settings.jobs_api_base_url = "https://api.example.local"
    settings.jobs_worker_update_token = SecretStr("worker-token")

    worker = JobsWorker(
        settings=settings,
        transfer_service=_FakeTransferService(),  # type: ignore[arg-type]
    )
    should_delete = worker._handle_message(
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


def test_worker_executes_transfer_process_and_posts_running_then_succeeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    monkeypatch.setattr(
        "nova_file_api.worker.boto3.client",
        lambda service_name, **kwargs: fake_sqs,
    )
    monkeypatch.setattr(
        "nova_file_api.worker.httpx.Client",
        lambda **kwargs: fake_http,
    )

    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_runtime_mode = "worker"
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = "https://example.local/queue"
    settings.jobs_api_base_url = "https://api.example.local"
    settings.jobs_worker_update_token = SecretStr("worker-token")

    worker = JobsWorker(
        settings=settings,
        transfer_service=transfer_service,  # type: ignore[arg-type]
    )
    should_delete = worker._handle_message(
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


def test_worker_retryable_execution_failure_leaves_message_unacked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    transfer_service._error = upstream_s3_error(
        "failed to copy upload object to export key"
    )

    monkeypatch.setattr(
        "nova_file_api.worker.boto3.client",
        lambda service_name, **kwargs: fake_sqs,
    )
    monkeypatch.setattr(
        "nova_file_api.worker.httpx.Client",
        lambda **kwargs: fake_http,
    )

    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_runtime_mode = "worker"
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = "https://example.local/queue"
    settings.jobs_api_base_url = "https://api.example.local"
    settings.jobs_worker_update_token = SecretStr("worker-token")

    worker = JobsWorker(
        settings=settings,
        transfer_service=transfer_service,  # type: ignore[arg-type]
    )
    message = {
        "MessageId": "msg-3",
        "ReceiptHandle": "receipt-3",
        "Body": _worker_message_body(job_id="job-2"),
        "Attributes": {"ApproximateReceiveCount": "2"},
    }

    should_delete = worker._handle_message(message=message)

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


def test_worker_leaves_message_unacked_when_running_update_retries_exhausted(
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
                409,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
            httpx.Response(
                409,
                request=httpx.Request(
                    "POST",
                    "https://api.example.local/v1/internal/jobs/job-2/result",
                ),
            ),
        ]
    )
    transfer_service = _FakeTransferService()

    monkeypatch.setattr(
        "nova_file_api.worker.boto3.client",
        lambda service_name, **kwargs: fake_sqs,
    )
    monkeypatch.setattr(
        "nova_file_api.worker.httpx.Client",
        lambda **kwargs: fake_http,
    )
    monkeypatch.setattr("nova_file_api.worker.time.sleep", lambda _: None)
    monkeypatch.setattr(
        "nova_file_api.worker.random.uniform",
        lambda _lower, _upper: 1.0,
    )

    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_runtime_mode = "worker"
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = "https://example.local/queue"
    settings.jobs_api_base_url = "https://api.example.local"
    settings.jobs_worker_update_token = SecretStr("worker-token")

    worker = JobsWorker(
        settings=settings,
        transfer_service=transfer_service,  # type: ignore[arg-type]
    )
    should_delete = worker._handle_message(
        message={
            "MessageId": "msg-4",
            "ReceiptHandle": "receipt-4",
            "Body": _worker_message_body(job_id="job-2"),
            "Attributes": {"ApproximateReceiveCount": "1"},
        }
    )

    assert should_delete is False
    assert transfer_service.calls == []
    assert len(fake_http.posts) == 3
    assert all(
        item["json"] == {"status": "running", "result": None, "error": None}
        for item in fake_http.posts
    )


def test_worker_retries_running_update_until_accepted(
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

    monkeypatch.setattr(
        "nova_file_api.worker.boto3.client",
        lambda service_name, **kwargs: fake_sqs,
    )
    monkeypatch.setattr(
        "nova_file_api.worker.httpx.Client",
        lambda **kwargs: fake_http,
    )
    monkeypatch.setattr(
        "nova_file_api.worker.time.sleep",
        lambda delay: sleep_calls.append(delay),
    )
    monkeypatch.setattr(
        "nova_file_api.worker.random.uniform",
        lambda _lower, _upper: 1.0,
    )

    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_runtime_mode = "worker"
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = "https://example.local/queue"
    settings.jobs_api_base_url = "https://api.example.local"
    settings.jobs_worker_update_token = SecretStr("worker-token")

    worker = JobsWorker(
        settings=settings,
        transfer_service=transfer_service,  # type: ignore[arg-type]
    )
    should_delete = worker._handle_message(
        message={
            "MessageId": "msg-5",
            "ReceiptHandle": "receipt-5",
            "Body": _worker_message_body(job_id="job-2"),
            "Attributes": {"ApproximateReceiveCount": "1"},
        }
    )

    assert should_delete is True
    assert sleep_calls == [0.25, 0.5]
    assert transfer_service.calls == [
        {
            "source_bucket": "nova-bucket",
            "source_key": "uploads/scope-1/source.csv",
            "scope_id": "scope-1",
            "job_id": "job-2",
            "filename": "source.csv",
        }
    ]
    assert len(fake_http.posts) == 4


def test_worker_leaves_message_unacked_when_terminal_update_is_rejected(
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

    monkeypatch.setattr(
        "nova_file_api.worker.boto3.client",
        lambda service_name, **kwargs: fake_sqs,
    )
    monkeypatch.setattr(
        "nova_file_api.worker.httpx.Client",
        lambda **kwargs: fake_http,
    )
    monkeypatch.setattr("nova_file_api.worker.time.sleep", lambda _: None)
    monkeypatch.setattr(
        "nova_file_api.worker.random.uniform",
        lambda _lower, _upper: 1.0,
    )

    settings = Settings()
    settings.jobs_enabled = True
    settings.jobs_runtime_mode = "worker"
    settings.jobs_queue_backend = JobsQueueBackend.SQS
    settings.jobs_sqs_queue_url = "https://example.local/queue"
    settings.jobs_api_base_url = "https://api.example.local"
    settings.jobs_worker_update_token = SecretStr("worker-token")

    worker = JobsWorker(
        settings=settings,
        transfer_service=transfer_service,  # type: ignore[arg-type]
    )
    should_delete = worker._handle_message(
        message={
            "MessageId": "msg-6",
            "ReceiptHandle": "receipt-6",
            "Body": _worker_message_body(job_id="job-2"),
            "Attributes": {"ApproximateReceiveCount": "1"},
        }
    )

    assert should_delete is False
    assert transfer_service.calls == [
        {
            "source_bucket": "nova-bucket",
            "source_key": "uploads/scope-1/source.csv",
            "scope_id": "scope-1",
            "job_id": "job-2",
            "filename": "source.csv",
        }
    ]
    assert fake_http.posts[0]["json"] == {
        "status": "running",
        "result": None,
        "error": None,
    }
    assert all(
        item["json"]
        == {
            "status": "succeeded",
            "result": {
                "export_key": "exports/scope-1/job-2/source.csv",
                "download_filename": "source.csv",
            },
            "error": None,
        }
        for item in fake_http.posts[1:]
    )
