"""Queued multipart-copy orchestration for large export workloads."""

from __future__ import annotations

import json
import math
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError

from nova_runtime_support.export_copy_parts import (
    ExportCopyPartRecord,
    ExportCopyPartRepository,
    ExportCopyPartStatus,
)
from nova_runtime_support.export_models import ExportRecord, ExportStatus
from nova_runtime_support.export_runtime import ExportMetrics, ExportRepository
from nova_runtime_support.export_utils import (
    _multipart_copy_create_upload_kwargs,
    _multipart_copy_part_size_bytes,
    _sanitize_filename,
)

_SQS_BATCH_SIZE = 10
_COPY_PART_RECORD_TTL_SECONDS = 14 * 24 * 60 * 60


class ExportCopyStrategy(StrEnum):
    """Supported export-copy execution lanes."""

    INLINE = "inline"
    WORKER = "worker"


@dataclass(slots=True, frozen=True)
class PreparedExportCopy:
    """Prepared export-copy plan derived from the source object."""

    export_key: str
    download_filename: str
    source_size_bytes: int
    copy_part_size_bytes: int
    copy_part_count: int
    strategy: ExportCopyStrategy


@dataclass(slots=True, frozen=True)
class QueuedExportCopyState:
    """Runtime state persisted in Step Functions for a queued copy."""

    export_key: str
    upload_id: str
    copy_part_count: int
    copy_part_size_bytes: int


@dataclass(slots=True, frozen=True)
class ExportCopyPollResult:
    """Polled view of queued export copy progress."""

    state: str
    completed_parts: int
    total_parts: int
    output_key: str | None = None
    download_filename: str | None = None


@dataclass(slots=True, frozen=True)
class ExportCopyTaskMessage:
    """SQS payload for one multipart-copy part range."""

    export_id: str
    source_key: str
    export_key: str
    upload_id: str
    part_number: int
    start_byte: int
    end_byte: int

    def as_dict(self) -> dict[str, object]:
        """Serialize one worker message to a JSON-safe mapping."""
        return {
            "export_id": self.export_id,
            "source_key": self.source_key,
            "export_key": self.export_key,
            "upload_id": self.upload_id,
            "part_number": self.part_number,
            "start_byte": self.start_byte,
            "end_byte": self.end_byte,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ExportCopyTaskMessage:
        """Build one worker message from a decoded JSON payload."""
        return cls(
            export_id=_require_non_empty_str(
                payload.get("export_id"), field="export_id"
            ),
            source_key=_require_non_empty_str(
                payload.get("source_key"), field="source_key"
            ),
            export_key=_require_non_empty_str(
                payload.get("export_key"), field="export_key"
            ),
            upload_id=_require_non_empty_str(
                payload.get("upload_id"), field="upload_id"
            ),
            part_number=_coerce_int(payload["part_number"]),
            start_byte=_coerce_int(payload["start_byte"]),
            end_byte=_coerce_int(payload["end_byte"]),
        )


class SqsClient(Protocol):
    """Subset of SQS client operations used by the queued copy lane."""

    async def send_message_batch(self, **kwargs: object) -> dict[str, object]:
        """Publish a batch of messages."""
        ...


class LargeExportCopyCoordinator:
    """Coordinate the queued export-copy lane and its worker tasks."""

    def __init__(
        self,
        *,
        bucket: str,
        upload_prefix: str,
        export_prefix: str,
        copy_part_size_bytes: int,
        worker_threshold_bytes: int,
        max_attempts: int,
        queue_url: str,
        s3_client: Any,
        sqs_client: SqsClient,
        export_repository: ExportRepository,
        export_copy_part_repository: ExportCopyPartRepository,
        metrics: ExportMetrics,
    ) -> None:
        """Initialize the queued export-copy coordinator and its backends.

        Args:
            bucket: Target S3 bucket for uploads and export objects.
            upload_prefix: Prefix for scoped upload keys.
            export_prefix: Prefix for export object keys.
            copy_part_size_bytes: Preferred multipart part size for copies.
            worker_threshold_bytes: Byte size threshold for the worker lane.
            max_attempts: Maximum part-copy attempts before failing the export.
            queue_url: SQS queue URL for part-copy work items.
            s3_client: Async S3 client for head, multipart, and copy operations.
            sqs_client: Async SQS client for publishing worker messages.
            export_repository: Durable export record store.
            export_copy_part_repository: Per-part copy state store.
            metrics: EMF metrics sink for worker observability.

        """
        self.bucket = bucket
        self.upload_prefix = _normalize_prefix(upload_prefix)
        self.export_prefix = _normalize_prefix(export_prefix)
        self.copy_part_size_bytes = copy_part_size_bytes
        self.worker_threshold_bytes = worker_threshold_bytes
        self.max_attempts = max_attempts
        self.queue_url = queue_url
        self._s3 = s3_client
        self._sqs = sqs_client
        self._exports = export_repository
        self._parts = export_copy_part_repository
        self._metrics = metrics

    async def prepare(
        self,
        *,
        export: ExportRecord,
    ) -> PreparedExportCopy:
        """Resolve copy strategy and durable planning metadata.

        Args:
            export: Export record to plan against.

        Returns:
            Prepared sizes, keys, part counts, and inline vs worker strategy.

        Raises:
            ValueError: If the source object is missing or invalid.
            RuntimeError: If S3 head-object or planning fails unexpectedly.
        """
        self._assert_upload_scope(
            key=export.source_key, scope_id=export.scope_id
        )
        source_object = await self._head_object(key=export.source_key)
        source_size_bytes = _require_non_negative_int(
            source_object.get("ContentLength"),
            error_message="source upload object is missing content length",
        )
        download_filename = _sanitize_filename(
            export.filename or Path(export.source_key).name
        )
        copy_part_size_bytes = _multipart_copy_part_size_bytes(
            source_size_bytes=source_size_bytes,
            preferred_part_size_bytes=self.copy_part_size_bytes,
        )
        copy_part_count = max(
            1, math.ceil(source_size_bytes / copy_part_size_bytes)
        )
        strategy = (
            ExportCopyStrategy.WORKER
            if source_size_bytes > self.worker_threshold_bytes
            else ExportCopyStrategy.INLINE
        )
        return PreparedExportCopy(
            export_key=_new_export_key(
                export_prefix=self.export_prefix,
                scope_id=export.scope_id,
                export_id=export.export_id,
                filename=download_filename,
            ),
            download_filename=download_filename,
            source_size_bytes=source_size_bytes,
            copy_part_size_bytes=copy_part_size_bytes,
            copy_part_count=copy_part_count,
            strategy=strategy,
        )

    async def start(
        self,
        *,
        export: ExportRecord,
        prepared: PreparedExportCopy,
    ) -> QueuedExportCopyState:
        """Create the destination MPU, persist part state, and enqueue work.

        Args:
            export: Current export row (expected status compatible with update).
            prepared: Output of :meth:`prepare` for this export.

        Returns:
            Queued state including MPU id and part sizing.

        Raises:
            RuntimeError: If the queue is not configured, updates race, or
                manifest creation fails.
            ValueError: If the source object cannot be read.
        """
        if not self.queue_url.strip():
            raise RuntimeError("export copy queue url is not configured")
        existing_state = _queued_state_from_export(export)
        if existing_state is not None:
            await self._ensure_manifest(
                export=export,
                source_size_bytes=(
                    export.source_size_bytes or prepared.source_size_bytes
                ),
                state=existing_state,
            )
            return existing_state
        source_object = await self._head_object(key=export.source_key)
        create_upload_output = await self._s3.create_multipart_upload(
            **_multipart_copy_create_upload_kwargs(
                bucket=self.bucket,
                key=prepared.export_key,
                source_object=source_object,
            )
        )
        upload_id = _optional_str(create_upload_output.get("UploadId"))
        if upload_id is None:
            raise RuntimeError(
                "multipart export copy response missing upload id"
            )
        queued_state = QueuedExportCopyState(
            export_key=prepared.export_key,
            upload_id=upload_id,
            copy_part_count=prepared.copy_part_count,
            copy_part_size_bytes=prepared.copy_part_size_bytes,
        )
        persisted_export = export.model_copy(
            update={
                "source_size_bytes": prepared.source_size_bytes,
                "copy_strategy": prepared.strategy.value,
                "copy_export_key": queued_state.export_key,
                "copy_upload_id": queued_state.upload_id,
                "copy_part_size_bytes": queued_state.copy_part_size_bytes,
                "copy_part_count": queued_state.copy_part_count,
            }
        )
        updated = await self._exports.update_if_status(
            record=persisted_export,
            expected_status=export.status,
        )
        if not updated:
            latest = await self._exports.get(export.export_id)
            await self._abort_multipart_upload(
                upload_id=queued_state.upload_id,
                export_key=queued_state.export_key,
            )
            if latest is not None:
                latest_state = _queued_state_from_export(latest)
                if latest_state is not None:
                    await self._ensure_manifest(
                        export=latest,
                        source_size_bytes=(
                            latest.source_size_bytes
                            or prepared.source_size_bytes
                        ),
                        state=latest_state,
                    )
                    return latest_state
            raise RuntimeError(
                "export copy state changed before queued work could start"
            )
        await self._ensure_manifest(
            export=persisted_export,
            source_size_bytes=prepared.source_size_bytes,
            state=queued_state,
        )
        return queued_state

    async def poll(
        self,
        *,
        export: ExportRecord,
        upload_id: str,
        export_key: str,
        download_filename: str,
    ) -> ExportCopyPollResult:
        """Return queued-copy progress and finalize the MPU when complete.

        Args:
            export: Latest export row (for cancellation and metrics).
            upload_id: Destination multipart upload id.
            export_key: Destination object key for the export copy.
            download_filename: Filename to expose when the copy completes.

        Returns:
            Poll snapshot with counts; ``state`` is ``ready`` when complete.

        Raises:
            RuntimeError: If part state is missing, parts fail permanently, or
                completion fails.
        """
        if export.status == ExportStatus.CANCELLED:
            await self._abort_multipart_upload(
                upload_id=upload_id,
                export_key=export_key,
            )
            return ExportCopyPollResult(
                state=ExportStatus.CANCELLED.value,
                completed_parts=0,
                total_parts=0,
            )
        part_records = await self._parts.list_for_export(
            export_id=export.export_id
        )
        if not part_records:
            raise RuntimeError("queued export copy part state is missing")
        completed_parts = [
            record
            for record in part_records
            if record.status == ExportCopyPartStatus.COPIED
        ]
        failed_parts = [
            record
            for record in part_records
            if record.status == ExportCopyPartStatus.FAILED
            and record.attempts >= self.max_attempts
        ]
        if failed_parts:
            await self._abort_multipart_upload(
                upload_id=upload_id,
                export_key=export_key,
            )
            raise RuntimeError(
                "queued export copy exhausted worker retries for one "
                "or more parts"
            )
        if len(completed_parts) != len(part_records):
            return ExportCopyPollResult(
                state="pending",
                completed_parts=len(completed_parts),
                total_parts=len(part_records),
            )
        try:
            await self._s3.complete_multipart_upload(
                Bucket=self.bucket,
                Key=export_key,
                UploadId=upload_id,
                MultipartUpload={
                    "Parts": [
                        {
                            "ETag": cast(str, record.etag),
                            "PartNumber": record.part_number,
                        }
                        for record in sorted(
                            completed_parts,
                            key=lambda record: record.part_number,
                        )
                    ]
                },
            )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code not in {"404", "NoSuchUpload", "NotFound"}:
                raise RuntimeError(
                    "failed to finalize queued export multipart copy"
                ) from exc
            if not await self._export_object_exists(key=export_key):
                raise RuntimeError(
                    "failed to finalize queued export multipart copy"
                ) from exc
        except BotoCoreError as exc:
            raise RuntimeError(
                "failed to finalize queued export multipart copy"
            ) from exc
        self._metrics.emit_emf(
            metric_name="exports_worker_finalize_total",
            value=1.0,
            unit="Count",
            dimensions={"source": "export_copy_worker"},
        )
        return ExportCopyPollResult(
            state="ready",
            completed_parts=len(completed_parts),
            total_parts=len(part_records),
            output_key=export_key,
            download_filename=download_filename,
        )

    async def process_message_batch(
        self,
        *,
        messages: list[tuple[str, ExportCopyTaskMessage]],
    ) -> list[str]:
        """Process one SQS batch and return the failed message identifiers.

        Args:
            messages: Pairs of SQS message id and decoded payload.

        Returns:
            Message ids that should be retried or sent to the DLQ.

        """
        failures: list[str] = []
        for message_id, payload in messages:
            try:
                await self._process_message(payload=payload)
            except Exception:
                with suppress(Exception):
                    await self._parts.mark_failed(
                        export_id=payload.export_id,
                        part_number=payload.part_number,
                        error="upload_part_copy_failed",
                    )
                failures.append(message_id)
        return failures

    async def _process_message(self, *, payload: ExportCopyTaskMessage) -> None:
        export = await self._exports.get(payload.export_id)
        if export is None:
            return
        if export.status in {
            ExportStatus.CANCELLED,
            ExportStatus.FAILED,
            ExportStatus.SUCCEEDED,
        }:
            return
        claimed = await self._parts.claim(
            export_id=payload.export_id,
            part_number=payload.part_number,
            upload_id=payload.upload_id,
            source_key=payload.source_key,
            export_key=payload.export_key,
        )
        if claimed is None or claimed.status == ExportCopyPartStatus.COPIED:
            return
        if (
            claimed.upload_id != payload.upload_id
            or claimed.export_key != payload.export_key
            or claimed.source_key != payload.source_key
        ):
            await self._parts.mark_failed(
                export_id=payload.export_id,
                part_number=payload.part_number,
                error="stale_copy_message",
            )
            raise RuntimeError("queued export copy message payload is stale")
        if (
            claimed.start_byte != payload.start_byte
            or claimed.end_byte != payload.end_byte
        ):
            await self._parts.mark_failed(
                export_id=payload.export_id,
                part_number=payload.part_number,
                error="invalid_byte_range",
            )
            raise RuntimeError(
                "queued export copy message byte range does not match claim"
            )
        if claimed.attempts >= self.max_attempts:
            await self._parts.mark_failed(
                export_id=payload.export_id,
                part_number=payload.part_number,
                error="max_attempts_exceeded",
            )
            return
        response = await self._s3.upload_part_copy(
            Bucket=self.bucket,
            CopySource={"Bucket": self.bucket, "Key": payload.source_key},
            CopySourceRange=f"bytes={payload.start_byte}-{payload.end_byte}",
            Key=payload.export_key,
            PartNumber=payload.part_number,
            UploadId=payload.upload_id,
        )
        copy_result = cast(dict[str, Any], response.get("CopyPartResult"))
        etag = _optional_str(copy_result.get("ETag") if copy_result else None)
        if etag is None:
            raise RuntimeError("multipart export copy part etag is missing")
        await self._parts.mark_copied(
            export_id=payload.export_id,
            part_number=payload.part_number,
            etag=etag,
        )

    async def _publish_messages(
        self,
        messages: list[ExportCopyTaskMessage],
    ) -> None:
        for index in range(0, len(messages), _SQS_BATCH_SIZE):
            batch = messages[index : index + _SQS_BATCH_SIZE]
            response = await self._sqs.send_message_batch(
                QueueUrl=self.queue_url,
                Entries=[
                    {
                        "Id": str(item.part_number),
                        "MessageBody": json.dumps(
                            item.as_dict(),
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    }
                    for item in batch
                ],
            )
            failed = cast(list[dict[str, Any]], response.get("Failed", []))
            if failed:
                raise RuntimeError(
                    "failed to publish export copy worker messages"
                )

    async def _head_object(self, *, key: str) -> dict[str, Any]:
        try:
            output = await self._s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise ValueError("source upload object not found") from exc
            raise RuntimeError(
                "failed to inspect source upload object"
            ) from exc
        except BotoCoreError as exc:
            raise RuntimeError(
                "failed to inspect source upload object"
            ) from exc
        return cast(dict[str, Any], output)

    async def _ensure_manifest(
        self,
        *,
        export: ExportRecord,
        source_size_bytes: int,
        state: QueuedExportCopyState,
    ) -> None:
        now = _utc_now()
        expires_at_epoch = int(now.timestamp()) + _COPY_PART_RECORD_TTL_SECONDS
        existing_records = {
            record.part_number: record
            for record in await self._parts.list_for_export(
                export_id=export.export_id
            )
        }
        records_to_write: list[ExportCopyPartRecord] = []
        messages: list[ExportCopyTaskMessage] = []
        for part_number, start_byte in enumerate(
            range(0, source_size_bytes, state.copy_part_size_bytes),
            start=1,
        ):
            end_byte = min(
                source_size_bytes - 1,
                start_byte + state.copy_part_size_bytes - 1,
            )
            existing = existing_records.get(part_number)
            desired_record = ExportCopyPartRecord(
                export_id=export.export_id,
                part_number=part_number,
                source_key=export.source_key,
                export_key=state.export_key,
                upload_id=state.upload_id,
                start_byte=start_byte,
                end_byte=end_byte,
                status=ExportCopyPartStatus.QUEUED,
                attempts=0,
                created_at=now,
                updated_at=now,
                expires_at_epoch=expires_at_epoch,
            )
            if (
                existing is None
                or existing.upload_id != state.upload_id
                or existing.export_key != state.export_key
                or existing.source_key != export.source_key
            ):
                records_to_write.append(desired_record)
            messages.append(
                ExportCopyTaskMessage(
                    export_id=export.export_id,
                    source_key=export.source_key,
                    export_key=state.export_key,
                    upload_id=state.upload_id,
                    part_number=part_number,
                    start_byte=start_byte,
                    end_byte=end_byte,
                )
            )
        if records_to_write:
            await self._parts.create_many(records_to_write)
        await self._publish_messages(messages)
        self._metrics.emit_emf(
            metric_name="exports_worker_parts_enqueued_total",
            value=float(len(messages)),
            unit="Count",
            dimensions={"source": "export_copy_worker"},
        )

    async def _abort_multipart_upload(
        self,
        *,
        upload_id: str,
        export_key: str,
    ) -> None:
        try:
            await self._s3.abort_multipart_upload(
                Bucket=self.bucket,
                Key=export_key,
                UploadId=upload_id,
            )
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code not in {"404", "NoSuchUpload", "NotFound"}:
                raise RuntimeError(
                    "failed to abort queued export multipart copy"
                ) from exc
        except BotoCoreError as exc:
            raise RuntimeError(
                "failed to abort queued export multipart copy"
            ) from exc

    async def _export_object_exists(self, *, key: str) -> bool:
        try:
            await self._s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise RuntimeError(
                "failed to inspect finalized export object"
            ) from exc
        except BotoCoreError as exc:
            raise RuntimeError(
                "failed to inspect finalized export object"
            ) from exc
        return True

    def _assert_upload_scope(self, *, key: str, scope_id: str) -> None:
        expected_prefix = f"{self.upload_prefix}{scope_id}/"
        if not key.startswith(expected_prefix):
            raise ValueError("key is outside caller upload scope")


def _normalize_prefix(prefix: str) -> str:
    normalized = prefix.strip()
    if normalized and not normalized.endswith("/"):
        normalized = f"{normalized}/"
    return normalized


def _new_export_key(
    *,
    export_prefix: str,
    scope_id: str,
    export_id: str,
    filename: str,
) -> str:
    stable_export_id = "".join(
        character
        for character in export_id.strip()
        if character.isalnum() or character in {"-", "_"}
    )
    if not stable_export_id:
        stable_export_id = uuid4().hex
    return f"{export_prefix}{scope_id}/{stable_export_id}/{filename}"


def _optional_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _require_non_empty_str(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field} must be a non-empty string")
    return value


def _require_non_negative_int(value: object, *, error_message: str) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            parsed = -1
        if parsed >= 0:
            return parsed
    raise RuntimeError(error_message)


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("boolean values are not valid integers")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError("value must be an integer-compatible type")


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _queued_state_from_export(
    export: ExportRecord,
) -> QueuedExportCopyState | None:
    if (
        export.copy_upload_id is None
        or export.copy_export_key is None
        or export.copy_part_count is None
        or export.copy_part_size_bytes is None
    ):
        return None
    return QueuedExportCopyState(
        export_key=export.copy_export_key,
        upload_id=export.copy_upload_id,
        copy_part_count=export.copy_part_count,
        copy_part_size_bytes=export.copy_part_size_bytes,
    )


__all__ = [
    "ExportCopyPollResult",
    "ExportCopyStrategy",
    "ExportCopyTaskMessage",
    "LargeExportCopyCoordinator",
    "PreparedExportCopy",
    "QueuedExportCopyState",
    "SqsClient",
]
