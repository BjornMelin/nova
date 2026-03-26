"""SQS worker entrypoint for export workflow execution."""

from __future__ import annotations

import asyncio
import json
import secrets
import signal
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

import structlog
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.activity import ActivityStore
from nova_file_api.aws import new_aioboto3_session
from nova_file_api.config import Settings
from nova_file_api.dependencies import (
    build_activity_store,
    build_export_publisher,
    build_export_repository,
    build_export_service,
    build_metrics,
)
from nova_file_api.errors import FileTransferError
from nova_file_api.exports import ExportService
from nova_file_api.models import (
    ActivityStoreBackend,
    ExportOutput,
    ExportStatus,
    JobsRepositoryBackend,
    Principal,
)
from nova_file_api.transfer import ExportCopyResult, TransferService

_RECEIVE_ERROR_BACKOFF_SECONDS = 2.0
_RESULT_UPDATE_MAX_ATTEMPTS = 3
_RESULT_UPDATE_BASE_DELAY_SECONDS = 0.25
_RESULT_UPDATE_MAX_DELAY_SECONDS = 2.0
_RETRYABLE_RESULT_STATUS_CODES = {404, 409, 500, 502, 503, 504}
_WORKER_RUNTIME_MODE = "worker"
_MIN_VISIBILITY_EXTENSION_INTERVAL_SECONDS = 0.5
_VISIBILITY_EXTENSION_RETRY_DELAY_SECONDS = 1.0
_SQS_VISIBILITY_TIMEOUT_MAX_SECONDS = 43_200
_WORKER_PRINCIPAL = Principal(
    subject="system:exports-worker",
    scope_id="system:exports-worker",
)

_T = TypeVar("_T")


@dataclass(slots=True, frozen=True)
class WorkerExportMessage:
    """Normalized queue payload consumed by the worker loop."""

    export_id: str
    scope_id: str
    source_key: str
    filename: str
    created_at: datetime

    @classmethod
    def from_body(cls, *, body: str) -> WorkerExportMessage:
        """Parse and validate an SQS message body payload.

        Args:
            body: Raw SQS message body JSON string.

        Returns:
            Parsed and validated worker job message.

        Raises:
            ValueError: If required fields are missing or ``created_at`` is
                invalid.
        """
        raw = json.loads(body)
        if not isinstance(raw, dict):
            raise TypeError("message body must be an object")
        export_id = str(raw.get("export_id", "")).strip()
        if not export_id:
            raise ValueError("message body is missing export_id")
        scope_id = str(raw.get("scope_id", "")).strip()
        if not scope_id:
            raise ValueError("message body is missing scope_id")
        source_key = str(raw.get("source_key", "")).strip()
        if not source_key:
            raise ValueError("message body is missing source_key")
        filename = str(raw.get("filename", "")).strip()
        if not filename:
            raise ValueError("message body is missing filename")
        try:
            created_at = _parse_iso8601(str(raw.get("created_at", "")).strip())
        except ValueError as exc:
            raise ValueError("message body created_at is invalid") from exc
        return cls(
            export_id=export_id,
            scope_id=scope_id,
            source_key=source_key,
            filename=filename,
            created_at=created_at,
        )


@dataclass(slots=True)
class _WorkerResultUpdateError(Exception):
    """Raised when a worker result update is not durably accepted."""

    # Keep dataclass fields for structured logging while still initializing
    # Exception args through Exception.__init__ in __post_init__.
    message: str
    retryable: bool
    status_code: int | None = None
    error_type: str | None = None

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


class JobsWorker:
    """Long-running SQS worker that writes job result updates directly."""

    def __init__(
        self,
        *,
        settings: Settings,
        transfer_service: TransferService | None = None,
        export_service: ExportService | None = None,
        activity_store: ActivityStore | None = None,
    ) -> None:
        """Initialize worker configuration and runtime state.

        Args:
            settings: Runtime configuration for queues, storage, and job wiring.
            transfer_service: Optional transfer executor; built at runtime when
                omitted.
            export_service: Optional export domain service; built at runtime
                when omitted.
            activity_store: Optional activity recorder; built at runtime when
                omitted.
        """
        self._settings = settings
        self._logger = structlog.get_logger("exports_worker")
        self._stop_requested = False
        self._queue_url = (settings.jobs_sqs_queue_url or "").strip()
        self._session = new_aioboto3_session()
        self._transfer_service = transfer_service
        self._export_service = export_service
        self._activity_store = activity_store
        self._runtime_transfer_service: TransferService | None = None
        self._runtime_export_service: ExportService | None = None
        self._runtime_activity_store: ActivityStore | None = None
        self._sqs: Any | None = None

    async def run(self) -> int:
        """Run the worker receive/process/ack loop until shutdown signal."""
        self._install_signal_handlers()
        self._logger.info(
            "exports_worker_started",
            queue_url=self._queue_url,
            queue_backend=self._settings.jobs_queue_backend.value,
        )
        s3_config = Config(
            s3={
                "use_accelerate_endpoint": (
                    self._settings.file_transfer_use_accelerate_endpoint
                )
            }
        )
        sqs_config = Config(
            retries={
                "mode": self._settings.jobs_sqs_retry_mode,
                "total_max_attempts": (
                    self._settings.jobs_sqs_retry_total_max_attempts
                ),
            }
        )
        needs_dynamodb_resource = (
            self._settings.jobs_repository_backend
            == JobsRepositoryBackend.DYNAMODB
            and self._export_service is None
        ) or (
            self._settings.activity_store_backend
            == ActivityStoreBackend.DYNAMODB
            and self._activity_store is None
        )
        try:
            async with AsyncExitStack() as stack:
                sqs_client = await stack.enter_async_context(
                    self._session.client("sqs", config=sqs_config)
                )
                s3_client = await stack.enter_async_context(
                    self._session.client("s3", config=s3_config)
                )
                dynamodb_resource = None
                if needs_dynamodb_resource:
                    dynamodb_resource = await stack.enter_async_context(
                        self._session.resource("dynamodb")
                    )
                self._sqs = sqs_client
                self._runtime_transfer_service = (
                    self._transfer_service
                    if self._transfer_service is not None
                    else TransferService(
                        settings=self._settings,
                        s3_client=s3_client,
                    )
                )
                self._runtime_export_service = (
                    self._export_service
                    if self._export_service is not None
                    else build_export_service(
                        export_repository=build_export_repository(
                            settings=self._settings,
                            dynamodb_resource=dynamodb_resource,
                        ),
                        export_publisher=build_export_publisher(
                            settings=self._settings,
                            sqs_client=sqs_client,
                        ),
                        metrics=build_metrics(settings=self._settings),
                    )
                )
                self._runtime_activity_store = (
                    self._activity_store
                    if self._activity_store is not None
                    else build_activity_store(
                        settings=self._settings,
                        dynamodb_resource=dynamodb_resource,
                    )
                )
                while not self._stop_requested:
                    messages = await self._receive_messages()
                    if not messages:
                        continue
                    for message in messages:
                        should_delete = await self._handle_message(
                            message=message
                        )
                        if should_delete:
                            await self._delete_message(message=message)
        finally:
            self._sqs = None
            self._runtime_transfer_service = None
            self._runtime_export_service = None
            self._runtime_activity_store = None
            self._logger.info("exports_worker_stopped")
        return 0

    def _install_signal_handlers(self) -> None:
        """Install signal handlers for graceful worker shutdown."""
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    signum, self._handle_stop_signal, signum, None
                )
            except (NotImplementedError, RuntimeError):
                signal.signal(signum, self._handle_stop_signal)

    def _handle_stop_signal(self, signum: int, _frame: Any) -> None:
        """Mark worker loop for shutdown when an OS signal is received."""
        self._stop_requested = True
        self._logger.info("exports_worker_stop_requested", signal=signum)

    async def _receive_messages(self) -> list[dict[str, Any]]:
        """Receive one poll batch from SQS with long polling enabled."""
        sqs_client = self._require_sqs()
        try:
            response = await sqs_client.receive_message(
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
                "exports_worker_receive_failed",
                error_type=type(exc).__name__,
            )
            await asyncio.sleep(_RECEIVE_ERROR_BACKOFF_SECONDS)
            return []
        messages = response.get("Messages")
        if not isinstance(messages, list):
            return []
        return [m for m in messages if isinstance(m, dict)]

    async def _handle_message(self, *, message: dict[str, Any]) -> bool:
        """Process one queue message and return whether to delete it."""
        message_id = str(message.get("MessageId", ""))
        body = str(message.get("Body", ""))
        receive_count = _approximate_receive_count(message=message)
        try:
            worker_message = WorkerExportMessage.from_body(body=body)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            self._logger.warning(
                "exports_worker_invalid_message",
                message_id=message_id,
                receive_count=receive_count,
                error_detail=str(exc),
            )
            return False

        async def _execute_copy_and_finalize() -> bool:
            try:
                transfer_service = self._require_transfer_service()
                if await self._publish_result(
                    export_id=worker_message.export_id,
                    status=ExportStatus.COPYING,
                    output=None,
                    error=None,
                    allow_terminal_conflict=True,
                ):
                    return True
                export = await transfer_service.copy_upload_to_export(
                    source_bucket=self._settings.file_transfer_bucket,
                    source_key=worker_message.source_key,
                    scope_id=worker_message.scope_id,
                    export_id=worker_message.export_id,
                    filename=worker_message.filename,
                )
            except FileTransferError as exc:
                if exc.status_code >= 500:
                    self._logger.warning(
                        "exports_worker_execution_retryable_failure",
                        message_id=message_id,
                        export_id=worker_message.export_id,
                        receive_count=receive_count,
                        error_code=exc.code,
                        error_detail=exc.message,
                    )
                    return False
                return await self._publish_terminal_result(
                    message_id=message_id,
                    receive_count=receive_count,
                    export_id=worker_message.export_id,
                    status=ExportStatus.FAILED,
                    output=None,
                    error=exc.message,
                )

            if await self._publish_result(
                export_id=worker_message.export_id,
                status=ExportStatus.FINALIZING,
                output=_success_output_from_export(export=export),
                error=None,
                allow_terminal_conflict=True,
            ):
                return True
            return await self._publish_terminal_result(
                message_id=message_id,
                receive_count=receive_count,
                export_id=worker_message.export_id,
                status=ExportStatus.SUCCEEDED,
                output=_success_output_from_export(export=export),
                error=None,
            )

        try:
            if await self._publish_result(
                export_id=worker_message.export_id,
                status=ExportStatus.VALIDATING,
                output=None,
                error=None,
                allow_terminal_conflict=True,
            ):
                self._logger.info(
                    "exports_worker_terminal_redelivery_acked",
                    message_id=message_id,
                    export_id=worker_message.export_id,
                    receive_count=receive_count,
                )
                return True
        except _WorkerResultUpdateError as exc:
            self._logger.warning(
                "exports_worker_validating_update_not_accepted",
                message_id=message_id,
                export_id=worker_message.export_id,
                receive_count=receive_count,
                retryable=exc.retryable,
                status_code=exc.status_code,
                error_type=exc.error_type,
                error_detail=str(exc),
            )
            if exc.status_code != 409:
                return False
            try:
                current_export = await self._require_export_service().get(
                    export_id=worker_message.export_id,
                    scope_id=worker_message.scope_id,
                )
            except FileTransferError as lookup_exc:
                self._logger.warning(
                    "exports_worker_resume_lookup_failed",
                    message_id=message_id,
                    export_id=worker_message.export_id,
                    receive_count=receive_count,
                    error_type=type(lookup_exc).__name__,
                    error_detail=str(lookup_exc),
                )
                return False
            if current_export.status in {
                ExportStatus.SUCCEEDED,
                ExportStatus.FAILED,
                ExportStatus.CANCELLED,
            }:
                self._logger.info(
                    "exports_worker_terminal_redelivery_acked",
                    message_id=message_id,
                    export_id=worker_message.export_id,
                    receive_count=receive_count,
                )
                return True
            if current_export.status == ExportStatus.FINALIZING:
                if current_export.output is None:
                    self._logger.warning(
                        "exports_worker_resume_missing_output",
                        message_id=message_id,
                        export_id=worker_message.export_id,
                        receive_count=receive_count,
                    )
                    return False
                return await self._publish_terminal_result(
                    message_id=message_id,
                    receive_count=receive_count,
                    export_id=worker_message.export_id,
                    status=ExportStatus.SUCCEEDED,
                    output=current_export.output,
                    error=None,
                )
            if current_export.status != ExportStatus.COPYING:
                self._logger.warning(
                    "exports_worker_unexpected_resume_state",
                    message_id=message_id,
                    export_id=worker_message.export_id,
                    receive_count=receive_count,
                    current_status=current_export.status.value,
                )
                return False
            return await self._run_with_visibility_extension(
                message=message,
                job_id=worker_message.export_id,
                operation=_execute_copy_and_finalize,
            )
        return await self._run_with_visibility_extension(
            message=message,
            job_id=worker_message.export_id,
            operation=_execute_copy_and_finalize,
        )

    async def _run_with_visibility_extension(
        self,
        *,
        message: dict[str, Any],
        job_id: str,
        operation: Callable[[], Awaitable[_T]],
    ) -> _T:
        """Run a long-lived operation while extending SQS visibility."""
        task = self._start_visibility_extension_task(
            message=message,
            job_id=job_id,
        )
        try:
            return await operation()
        finally:
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    def _start_visibility_extension_task(
        self,
        *,
        message: dict[str, Any],
        job_id: str,
    ) -> asyncio.Task[None] | None:
        """Start a heartbeat task for extending message visibility."""
        receipt_handle = str(message.get("ReceiptHandle", "")).strip()
        if not receipt_handle:
            return None
        visibility_timeout = self._settings.jobs_sqs_visibility_timeout_seconds
        if visibility_timeout <= 0:
            return None
        interval_seconds = max(
            _MIN_VISIBILITY_EXTENSION_INTERVAL_SECONDS,
            visibility_timeout / 2.0,
        )
        return asyncio.create_task(
            self._extend_visibility_loop(
                receipt_handle=receipt_handle,
                job_id=job_id,
                interval_seconds=interval_seconds,
            )
        )

    async def _extend_visibility_loop(
        self,
        *,
        receipt_handle: str,
        job_id: str,
        interval_seconds: float,
    ) -> None:
        """Heartbeat visibility timeout while long-running work is active."""
        retry_delay_seconds = min(
            _VISIBILITY_EXTENSION_RETRY_DELAY_SECONDS,
            interval_seconds,
        )
        await asyncio.sleep(interval_seconds)
        while True:
            try:
                await self._require_sqs().change_message_visibility(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=(
                        self._settings.jobs_sqs_visibility_timeout_seconds
                    ),
                )
            except (ClientError, BotoCoreError) as exc:
                if isinstance(
                    exc, ClientError
                ) and _is_visibility_timeout_ceiling_error(exc):
                    self._logger.warning(
                        "exports_worker_visibility_extension_ceiling_reached",
                        job_id=job_id,
                        max_visibility_seconds=_SQS_VISIBILITY_TIMEOUT_MAX_SECONDS,
                    )
                    return
                self._logger.warning(
                    "exports_worker_visibility_extension_failed",
                    job_id=job_id,
                    error_type=type(exc).__name__,
                )
                await asyncio.sleep(retry_delay_seconds)
                continue
            await asyncio.sleep(interval_seconds)

    async def _publish_terminal_result(
        self,
        *,
        message_id: str,
        receive_count: int | None,
        export_id: str,
        status: ExportStatus,
        output: ExportOutput | None,
        error: str | None,
    ) -> bool:
        """Publish a terminal export update and report delete eligibility."""
        try:
            await self._publish_result(
                export_id=export_id,
                status=status,
                output=output,
                error=error,
                allow_terminal_conflict=True,
            )
        except _WorkerResultUpdateError as exc:
            self._logger.warning(
                "exports_worker_result_update_not_accepted",
                message_id=message_id,
                export_id=export_id,
                receive_count=receive_count,
                retryable=exc.retryable,
                status_code=exc.status_code,
                error_type=exc.error_type,
                error_detail=exc.message,
            )
            return False
        self._logger.info(
            "exports_worker_message_completed",
            message_id=message_id,
            export_id=export_id,
            receive_count=receive_count,
            status=status.value,
        )
        return True

    async def _publish_result(
        self,
        *,
        export_id: str,
        status: ExportStatus,
        output: ExportOutput | None,
        error: str | None,
        allow_terminal_conflict: bool = False,
    ) -> bool:
        """Persist worker status through shared runtime services."""
        export_service = self._require_export_service()
        last_error: _WorkerResultUpdateError | None = None
        for attempt in range(1, _RESULT_UPDATE_MAX_ATTEMPTS + 1):
            try:
                export = await export_service.update_status(
                    export_id=export_id,
                    status=status,
                    output=output,
                    error=error,
                )
            except FileTransferError as exc:
                if (
                    allow_terminal_conflict
                    and self._is_terminal_result_update_conflict(
                        exc,
                        requested_status=status,
                    )
                ):
                    self._logger.info(
                        "exports_worker_update_already_terminal",
                        export_id=export_id,
                        current_status=str(
                            exc.details.get("current_status", "")
                        ),
                        requested_status=status.value,
                    )
                    return True
                retryable = exc.status_code in _RETRYABLE_RESULT_STATUS_CODES
                last_error = _WorkerResultUpdateError(
                    (
                        "worker result update was rejected transiently"
                        if retryable
                        else "worker result update was rejected permanently"
                    ),
                    retryable=retryable,
                    status_code=exc.status_code,
                    error_type=exc.code,
                )
                await self._record_job_result_update_failure(
                    export_id=export_id,
                    status=status,
                    error_detail=exc.message,
                )
                if not retryable:
                    raise last_error from exc
            except Exception as exc:
                await self._record_job_result_update_failure(
                    export_id=export_id,
                    status=status,
                    error_detail=f"{type(exc).__name__}: {exc}",
                )
                last_error = _WorkerResultUpdateError(
                    "worker result update failed",
                    retryable=True,
                    error_type=type(exc).__name__,
                )
            else:
                await self._record_job_result_update_success(export=export)
                return False
            if attempt == _RESULT_UPDATE_MAX_ATTEMPTS:
                assert last_error is not None
                raise last_error
            delay_seconds = _result_update_retry_delay_seconds(attempt=attempt)
            self._logger.warning(
                "exports_worker_result_update_retrying",
                export_id=export_id,
                status=status.value,
                attempt=attempt,
                max_attempts=_RESULT_UPDATE_MAX_ATTEMPTS,
                retryable=last_error.retryable if last_error else True,
                status_code=last_error.status_code if last_error else None,
                error_type=last_error.error_type if last_error else None,
                delay_seconds=delay_seconds,
            )
            await asyncio.sleep(delay_seconds)
        return False

    async def _delete_message(self, *, message: dict[str, Any]) -> None:
        """Delete handled message from SQS to finalize processing."""
        sqs_client = self._require_sqs()
        receipt_handle = str(message.get("ReceiptHandle", "")).strip()
        if not receipt_handle:
            self._logger.warning("exports_worker_missing_receipt_handle")
            return
        try:
            await sqs_client.delete_message(
                QueueUrl=self._queue_url,
                ReceiptHandle=receipt_handle,
            )
        except (ClientError, BotoCoreError) as exc:
            self._logger.exception(
                "exports_worker_delete_failed",
                error_type=type(exc).__name__,
            )

    def _require_sqs(self) -> Any:
        if self._sqs is None:
            raise RuntimeError("worker SQS client is not initialized")
        return self._sqs

    def _require_transfer_service(self) -> TransferService:
        if self._runtime_transfer_service is None:
            raise RuntimeError("worker transfer service is not initialized")
        return self._runtime_transfer_service

    def _require_export_service(self) -> ExportService:
        if self._runtime_export_service is None:
            raise RuntimeError("worker export service is not initialized")
        return self._runtime_export_service

    def _require_activity_store(self) -> ActivityStore:
        if self._runtime_activity_store is None:
            raise RuntimeError("worker activity store is not initialized")
        return self._runtime_activity_store

    async def _record_job_result_update_success(self, *, export: Any) -> None:
        """Emit the worker result-update activity event best-effort."""
        try:
            await self._require_activity_store().record(
                principal=_WORKER_PRINCIPAL,
                event_type="exports_result_update",
                details=(
                    "worker result update accepted "
                    f"for export_id={export.export_id} "
                    f"status={export.status.value}"
                ),
            )
        except Exception:
            self._logger.exception(
                "exports_result_update_activity_record_failed",
                export_id=export.export_id,
                status=export.status.value,
            )

    async def _record_job_result_update_failure(
        self,
        *,
        export_id: str,
        status: ExportStatus,
        error_detail: str,
    ) -> None:
        """Emit the worker result-update failure event best-effort."""
        try:
            await self._require_activity_store().record(
                principal=_WORKER_PRINCIPAL,
                event_type="exports_result_update_failure",
                details=(
                    "worker result update failed "
                    f"for export_id={export_id} status={status.value}: "
                    f"{error_detail}"
                ),
            )
        except Exception:
            self._logger.exception(
                "exports_result_update_failure_activity_record_failed",
                export_id=export_id,
                status=status.value,
            )

    @staticmethod
    def _is_terminal_result_update_conflict(
        exc: FileTransferError,
        *,
        requested_status: ExportStatus,
    ) -> bool:
        """Return whether a conflict means the export is already terminal."""
        if exc.code != "conflict" or exc.status_code != 409:
            return False
        if str(exc.details.get("requested_status", "")).strip() != (
            requested_status.value
        ):
            return False
        current_status = str(exc.details.get("current_status", "")).strip()
        return current_status in {
            ExportStatus.SUCCEEDED.value,
            ExportStatus.FAILED.value,
            ExportStatus.CANCELLED.value,
        }


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
    jitter = secrets.SystemRandom().uniform(0.75, 1.25)
    return float(delay_seconds * jitter)


def _is_visibility_timeout_ceiling_error(exc: ClientError) -> bool:
    """Return True when SQS rejects visibility extension at the 12h ceiling."""
    error = exc.response.get("Error", {})
    code = str(error.get("Code", "")).strip()
    message = str(error.get("Message", "")).lower()
    if code not in {
        "InvalidParameterValue",
        "AWS.SimpleQueueService.InvalidParameterValue",
    }:
        return False
    return "visibility" in message and (
        str(_SQS_VISIBILITY_TIMEOUT_MAX_SECONDS) in message
        or "maximum time left" in message
        or "maximum visibility timeout" in message
    )


def _success_output_from_export(
    *,
    export: ExportCopyResult,
) -> ExportOutput:
    return ExportOutput(
        key=export.export_key,
        download_filename=export.download_filename,
    )


async def main() -> int:
    """Package script entrypoint for the SQS worker process."""
    settings = Settings()
    if settings.jobs_runtime_mode != _WORKER_RUNTIME_MODE:
        raise ValueError(
            "JOBS_RUNTIME_MODE must be set to worker for nova-file-worker"
        )
    return await JobsWorker(settings=settings).run()


def cli() -> int:
    """Run the async worker entrypoint from a synchronous CLI boundary."""
    return asyncio.run(main())


if __name__ == "__main__":
    raise SystemExit(cli())
