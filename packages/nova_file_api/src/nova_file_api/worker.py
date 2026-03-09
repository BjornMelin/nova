"""SQS worker entrypoint for async job execution."""

from __future__ import annotations

import json
import random
import signal
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import boto3
import httpx
import structlog
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.config import Settings
from nova_file_api.errors import FileTransferError
from nova_file_api.models import TRANSFER_PROCESS_JOB_TYPE, JobStatus
from nova_file_api.transfer import ExportCopyResult, TransferService

_INTERNAL_RESULT_ROUTE_TEMPLATE = "/v1/internal/jobs/{job_id}/result"
_RECEIVE_ERROR_BACKOFF_SECONDS = 2.0
_RESULT_UPDATE_MAX_ATTEMPTS = 3
_RESULT_UPDATE_BASE_DELAY_SECONDS = 0.25
_RESULT_UPDATE_MAX_DELAY_SECONDS = 2.0
_RETRYABLE_RESULT_STATUS_CODES = {404, 409, 500, 502, 503, 504}
_WORKER_RUNTIME_MODE = "worker"


@dataclass(slots=True, frozen=True)
class WorkerJobMessage:
    """Normalized queue payload consumed by the worker loop."""

    job_id: str
    job_type: str
    scope_id: str
    payload: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_body(cls, *, body: str) -> WorkerJobMessage:
        """Parse and validate an SQS message body payload."""
        raw = json.loads(body)
        if not isinstance(raw, dict):
            raise ValueError("message body must be an object")
        if {"status", "result", "error"} & raw.keys():
            raise ValueError(
                "message body must not contain result-update fields"
            )
        job_id = str(raw.get("job_id", "")).strip()
        if not job_id:
            raise ValueError("message body is missing job_id")
        job_type = str(raw.get("job_type", "")).strip()
        if not job_type:
            raise ValueError("message body is missing job_type")
        scope_id = str(raw.get("scope_id", "")).strip()
        if not scope_id:
            raise ValueError("message body is missing scope_id")
        payload = raw.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("message body payload must be an object")
        try:
            created_at = _parse_iso8601(str(raw.get("created_at", "")).strip())
        except ValueError as exc:
            raise ValueError("message body created_at is invalid") from exc
        return cls(
            job_id=job_id,
            job_type=job_type,
            scope_id=scope_id,
            payload=payload,
            created_at=created_at,
        )


@dataclass(slots=True, frozen=True)
class TransferProcessPayload:
    """Payload required for the canonical transfer.process worker job."""

    bucket: str
    key: str
    filename: str
    size_bytes: int
    content_type: str | None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> TransferProcessPayload:
        """Parse and validate a transfer.process payload."""
        bucket = str(raw.get("bucket", "")).strip()
        if not bucket:
            raise ValueError("transfer.process payload is missing bucket")
        key = str(raw.get("key", "")).strip()
        if not key:
            raise ValueError("transfer.process payload is missing key")
        filename = str(raw.get("filename", "")).strip()
        if not filename:
            raise ValueError("transfer.process payload is missing filename")
        raw_size_bytes = raw.get("size_bytes")
        if not isinstance(raw_size_bytes, int) or raw_size_bytes <= 0:
            raise ValueError(
                "transfer.process payload size_bytes must be a positive integer"
            )
        raw_content_type = raw.get("content_type")
        content_type: str | None
        if raw_content_type is None:
            content_type = None
        elif isinstance(raw_content_type, str):
            content_type = raw_content_type.strip() or None
        else:
            raise ValueError(
                "transfer.process payload content_type must be a string or null"
            )
        return cls(
            bucket=bucket,
            key=key,
            filename=filename,
            size_bytes=raw_size_bytes,
            content_type=content_type,
        )


@dataclass(slots=True)
class _WorkerResultUpdateError(Exception):
    """Raised when a worker result callback is not durably accepted."""

    message: str
    retryable: bool
    status_code: int | None = None
    error_type: str | None = None

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


class JobsWorker:
    """Long-running SQS worker that posts job result updates to API."""

    def __init__(
        self,
        *,
        settings: Settings,
        transfer_service: TransferService | None = None,
    ) -> None:
        """Create queue and HTTP clients from worker settings."""
        self._settings = settings
        self._logger = structlog.get_logger("jobs_worker")
        self._stop_requested = False
        self._queue_url = (settings.jobs_sqs_queue_url or "").strip()
        self._transfer_service = transfer_service or TransferService(
            settings=settings
        )
        token = settings.jobs_worker_update_token
        worker_token = token.get_secret_value() if token is not None else ""
        self._sqs = boto3.client(
            "sqs",
            config=Config(
                retries={
                    "mode": settings.jobs_sqs_retry_mode,
                    "total_max_attempts": (
                        settings.jobs_sqs_retry_total_max_attempts
                    ),
                }
            ),
        )
        self._api = httpx.Client(
            base_url=(settings.jobs_api_base_url or "").rstrip("/"),
            timeout=10.0,
            headers={
                "X-Worker-Token": worker_token,
                "Content-Type": "application/json",
            },
        )

    def run(self) -> int:
        """Run the worker receive/process/ack loop until shutdown signal."""
        self._install_signal_handlers()
        self._logger.info(
            "jobs_worker_started",
            queue_url=self._queue_url,
            queue_backend=self._settings.jobs_queue_backend.value,
        )
        try:
            while not self._stop_requested:
                messages = self._receive_messages()
                if not messages:
                    continue
                for message in messages:
                    should_delete = self._handle_message(message=message)
                    if should_delete:
                        self._delete_message(message=message)
        finally:
            self._api.close()
            self._logger.info("jobs_worker_stopped")
        return 0

    def _install_signal_handlers(self) -> None:
        """Install signal handlers for graceful worker shutdown."""
        signal.signal(signal.SIGINT, self._handle_stop_signal)
        signal.signal(signal.SIGTERM, self._handle_stop_signal)

    def _handle_stop_signal(self, signum: int, _frame: Any) -> None:
        """Mark worker loop for shutdown when an OS signal is received."""
        self._stop_requested = True
        self._logger.info("jobs_worker_stop_requested", signal=signum)

    def _receive_messages(self) -> list[dict[str, Any]]:
        """Receive one poll batch from SQS with long polling enabled."""
        try:
            response = self._sqs.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=self._settings.jobs_sqs_max_number_of_messages,
                WaitTimeSeconds=self._settings.jobs_sqs_wait_time_seconds,
                VisibilityTimeout=(
                    self._settings.jobs_sqs_visibility_timeout_seconds
                ),
                MessageSystemAttributeNames=["ApproximateReceiveCount"],
            )
        except (ClientError, BotoCoreError) as exc:
            self._logger.exception(
                "jobs_worker_receive_failed",
                error_type=type(exc).__name__,
            )
            time.sleep(_RECEIVE_ERROR_BACKOFF_SECONDS)
            return []
        messages = response.get("Messages")
        if not isinstance(messages, list):
            return []
        return [m for m in messages if isinstance(m, dict)]

    def _handle_message(self, *, message: dict[str, Any]) -> bool:
        """Process one queue message and return whether to delete it."""
        message_id = str(message.get("MessageId", ""))
        body = str(message.get("Body", ""))
        receive_count = _approximate_receive_count(message=message)
        try:
            worker_message = WorkerJobMessage.from_body(body=body)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            self._logger.warning(
                "jobs_worker_invalid_message",
                message_id=message_id,
                receive_count=receive_count,
                error_detail=str(exc),
            )
            return False

        if worker_message.job_type != TRANSFER_PROCESS_JOB_TYPE:
            return self._publish_terminal_result(
                message_id=message_id,
                receive_count=receive_count,
                job_id=worker_message.job_id,
                status=JobStatus.FAILED,
                result=None,
                error=f"unsupported job type: {worker_message.job_type}",
            )

        try:
            payload = TransferProcessPayload.from_raw(worker_message.payload)
        except ValueError as exc:
            return self._publish_terminal_result(
                message_id=message_id,
                receive_count=receive_count,
                job_id=worker_message.job_id,
                status=JobStatus.FAILED,
                result=None,
                error=str(exc),
            )

        try:
            self._publish_result(
                job_id=worker_message.job_id,
                status=JobStatus.RUNNING,
                result=None,
                error=None,
            )
        except _WorkerResultUpdateError as exc:
            self._logger.warning(
                "jobs_worker_running_update_not_accepted",
                message_id=message_id,
                job_id=worker_message.job_id,
                receive_count=receive_count,
                retryable=exc.retryable,
                status_code=exc.status_code,
                error_type=exc.error_type,
                error_detail=str(exc),
            )
            return False

        try:
            export = self._transfer_service.copy_upload_to_export(
                source_bucket=payload.bucket,
                source_key=payload.key,
                scope_id=worker_message.scope_id,
                job_id=worker_message.job_id,
                filename=payload.filename,
            )
        except FileTransferError as exc:
            if exc.status_code >= 500:
                self._logger.warning(
                    "jobs_worker_execution_retryable_failure",
                    message_id=message_id,
                    job_id=worker_message.job_id,
                    receive_count=receive_count,
                    error_code=exc.code,
                    error_detail=exc.message,
                )
                return False
            return self._publish_terminal_result(
                message_id=message_id,
                receive_count=receive_count,
                job_id=worker_message.job_id,
                status=JobStatus.FAILED,
                result=None,
                error=exc.message,
            )

        return self._publish_terminal_result(
            message_id=message_id,
            receive_count=receive_count,
            job_id=worker_message.job_id,
            status=JobStatus.SUCCEEDED,
            result=_success_result_from_export(export=export),
            error=None,
        )

    def _publish_terminal_result(
        self,
        *,
        message_id: str,
        receive_count: int | None,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> bool:
        """Publish a terminal worker result and report delete eligibility."""
        try:
            self._publish_result(
                job_id=job_id,
                status=status,
                result=result,
                error=error,
            )
        except _WorkerResultUpdateError as exc:
            self._logger.warning(
                "jobs_worker_result_update_not_accepted",
                message_id=message_id,
                job_id=job_id,
                receive_count=receive_count,
                retryable=exc.retryable,
                status_code=exc.status_code,
                error_type=exc.error_type,
                error_detail=exc.message,
            )
            return False
        self._logger.info(
            "jobs_worker_message_completed",
            message_id=message_id,
            job_id=job_id,
            receive_count=receive_count,
            status=status.value,
        )
        return True

    def _publish_result(
        self,
        *,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        """Publish worker completion status to the internal result endpoint."""
        route = _INTERNAL_RESULT_ROUTE_TEMPLATE.format(job_id=job_id)
        payload = {"status": status.value, "result": result, "error": error}
        last_error: _WorkerResultUpdateError | None = None
        for attempt in range(1, _RESULT_UPDATE_MAX_ATTEMPTS + 1):
            try:
                response = self._api.post(route, json=payload)
            except httpx.HTTPError as exc:
                last_error = _WorkerResultUpdateError(
                    "worker result update request failed",
                    retryable=True,
                    error_type=type(exc).__name__,
                )
            else:
                if response.is_success:
                    return
                if response.status_code in _RETRYABLE_RESULT_STATUS_CODES:
                    last_error = _WorkerResultUpdateError(
                        "worker result update was rejected transiently",
                        retryable=True,
                        status_code=response.status_code,
                    )
                else:
                    raise _WorkerResultUpdateError(
                        "worker result update was rejected permanently",
                        retryable=False,
                        status_code=response.status_code,
                    )
            if attempt == _RESULT_UPDATE_MAX_ATTEMPTS:
                assert last_error is not None
                raise last_error
            delay_seconds = _result_update_retry_delay_seconds(attempt=attempt)
            self._logger.warning(
                "jobs_worker_result_update_retrying",
                job_id=job_id,
                status=status.value,
                attempt=attempt,
                max_attempts=_RESULT_UPDATE_MAX_ATTEMPTS,
                retryable=last_error.retryable if last_error else True,
                status_code=last_error.status_code if last_error else None,
                error_type=last_error.error_type if last_error else None,
                delay_seconds=delay_seconds,
            )
            time.sleep(delay_seconds)

    def _delete_message(self, *, message: dict[str, Any]) -> None:
        """Delete handled message from SQS to finalize processing."""
        receipt_handle = str(message.get("ReceiptHandle", "")).strip()
        if not receipt_handle:
            self._logger.warning("jobs_worker_missing_receipt_handle")
            return
        try:
            self._sqs.delete_message(
                QueueUrl=self._queue_url,
                ReceiptHandle=receipt_handle,
            )
        except (ClientError, BotoCoreError) as exc:
            self._logger.exception(
                "jobs_worker_delete_failed",
                error_type=type(exc).__name__,
            )


def _approximate_receive_count(*, message: dict[str, Any]) -> int | None:
    attributes = message.get("Attributes")
    if not isinstance(attributes, dict):
        return None
    raw = attributes.get("ApproximateReceiveCount")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _parse_iso8601(value: str) -> datetime:
    if not value:
        raise ValueError("created_at is missing")
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _result_update_retry_delay_seconds(*, attempt: int) -> float:
    delay_seconds = float(
        min(
            _RESULT_UPDATE_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
            _RESULT_UPDATE_MAX_DELAY_SECONDS,
        )
    )
    jitter = random.uniform(0.75, 1.25)
    return float(delay_seconds * jitter)


def _success_result_from_export(
    *,
    export: ExportCopyResult,
) -> dict[str, Any]:
    return {
        "export_key": export.export_key,
        "download_filename": export.download_filename,
    }


def main() -> int:
    """Package script entrypoint for the SQS worker process."""
    settings = Settings()
    if settings.jobs_runtime_mode != _WORKER_RUNTIME_MODE:
        raise ValueError(
            "JOBS_RUNTIME_MODE must be set to worker for nova-file-worker"
        )
    return JobsWorker(settings=settings).run()


if __name__ == "__main__":
    raise SystemExit(main())
