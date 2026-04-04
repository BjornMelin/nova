from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from botocore.exceptions import ClientError

from nova_runtime_support.export_copy_parts import (
    MemoryExportCopyPartRepository,
)
from nova_runtime_support.export_copy_worker import (
    ExportCopyStrategy,
    ExportCopyTaskMessage,
    LargeExportCopyCoordinator,
)
from nova_runtime_support.export_models import ExportRecord, ExportStatus
from nova_runtime_support.export_runtime import (
    MemoryExportRepository,
    NoopExportMetrics,
)


class _StubS3Client:
    def __init__(self, *, source_size_bytes: int) -> None:
        self.source_size_bytes = source_size_bytes
        self.create_calls: list[dict[str, object]] = []
        self.part_calls: list[dict[str, object]] = []
        self.complete_calls: list[dict[str, object]] = []
        self.abort_calls: list[dict[str, object]] = []
        self.complete_error: Exception | None = None
        self.export_object_exists = False

    async def head_object(self, **kwargs: object) -> dict[str, object]:
        key = kwargs.get("Key")
        if isinstance(key, str) and key.startswith("exports/"):
            if self.export_object_exists:
                return {"ContentLength": self.source_size_bytes}
            raise ClientError(
                {"Error": {"Code": "NotFound"}},
                "HeadObject",
            )
        return {
            "ContentLength": self.source_size_bytes,
            "ContentType": "text/csv",
        }

    async def create_multipart_upload(
        self, **kwargs: object
    ) -> dict[str, object]:
        self.create_calls.append(dict(kwargs))
        return {"UploadId": "worker-upload-id"}

    async def upload_part_copy(self, **kwargs: object) -> dict[str, object]:
        self.part_calls.append(dict(kwargs))
        return {
            "CopyPartResult": {"ETag": f"etag-{kwargs['PartNumber']}"},
        }

    async def complete_multipart_upload(
        self, **kwargs: object
    ) -> dict[str, object]:
        self.complete_calls.append(dict(kwargs))
        if self.complete_error is not None:
            raise self.complete_error
        return {"ETag": "final-etag"}

    async def abort_multipart_upload(
        self, **kwargs: object
    ) -> dict[str, object]:
        self.abort_calls.append(dict(kwargs))
        return {}


class _StubSqsClient:
    def __init__(self) -> None:
        self.batches: list[list[dict[str, object]]] = []

    async def send_message_batch(self, **kwargs: object) -> dict[str, object]:
        entries = cast(list[dict[str, object]], kwargs["Entries"])
        self.batches.append(list(entries))
        return {"Successful": entries, "Failed": []}


def _export_record(*, export_id: str = "export-1") -> ExportRecord:
    now = datetime.now(tz=UTC)
    return ExportRecord(
        export_id=export_id,
        scope_id="scope-1",
        request_id="req-1",
        source_key="uploads/scope-1/source.csv",
        filename="source.csv",
        status=ExportStatus.QUEUED,
        output=None,
        error=None,
        execution_arn=None,
        cancel_requested_at=None,
        source_size_bytes=None,
        copy_strategy=None,
        copy_export_key=None,
        copy_upload_id=None,
        copy_part_size_bytes=None,
        copy_part_count=None,
        copying_entered_at=None,
        finalizing_entered_at=None,
        created_at=now,
        updated_at=now,
    )


def _coordinator(
    *,
    source_size_bytes: int,
    export_repository: MemoryExportRepository,
    part_repository: MemoryExportCopyPartRepository | None = None,
    sqs_client: _StubSqsClient | None = None,
) -> tuple[
    LargeExportCopyCoordinator,
    _StubS3Client,
    _StubSqsClient,
    MemoryExportCopyPartRepository,
]:
    s3_client = _StubS3Client(source_size_bytes=source_size_bytes)
    resolved_sqs_client = sqs_client or _StubSqsClient()
    resolved_part_repository = (
        part_repository or MemoryExportCopyPartRepository()
    )
    coordinator = LargeExportCopyCoordinator(
        bucket="bucket",
        upload_prefix="uploads/",
        export_prefix="exports/",
        copy_part_size_bytes=2 * 1024 * 1024 * 1024,
        worker_threshold_bytes=50 * 1024 * 1024 * 1024,
        max_attempts=5,
        queue_url="https://queue.example.com/export-copy",
        s3_client=s3_client,
        sqs_client=resolved_sqs_client,
        export_repository=export_repository,
        export_copy_part_repository=resolved_part_repository,
        metrics=NoopExportMetrics(),
    )
    return coordinator, s3_client, resolved_sqs_client, resolved_part_repository


@pytest.mark.anyio
async def test_prepare_selects_worker_for_large_exports() -> None:
    repository = MemoryExportRepository()
    export = _export_record()
    await repository.create(export)
    coordinator, _s3_client, _sqs_client, _parts = _coordinator(
        source_size_bytes=60 * 1024 * 1024 * 1024,
        export_repository=repository,
    )

    prepared = await coordinator.prepare(export=export)

    assert prepared.strategy == ExportCopyStrategy.WORKER
    assert prepared.copy_part_count > 0
    assert prepared.export_key == "exports/scope-1/export-1/source.csv"


@pytest.mark.anyio
async def test_start_persists_part_state_and_batches_messages() -> None:
    repository = MemoryExportRepository()
    export = _export_record()
    await repository.create(export)
    coordinator, _s3_client, sqs_client, part_repository = _coordinator(
        source_size_bytes=60 * 1024 * 1024 * 1024,
        export_repository=repository,
    )
    prepared = await coordinator.prepare(export=export)

    queued = await coordinator.start(export=export, prepared=prepared)
    records = await part_repository.list_for_export(export_id=export.export_id)

    assert queued.upload_id == "worker-upload-id"
    assert queued.copy_part_count == len(records)
    assert len(sqs_client.batches) >= 1
    assert sum(len(batch) for batch in sqs_client.batches) == len(records)


@pytest.mark.anyio
async def test_process_message_batch_is_idempotent_for_copied_parts() -> None:
    export_repository = MemoryExportRepository()
    export = _export_record()
    await export_repository.create(export)
    part_repository = MemoryExportCopyPartRepository()
    coordinator, s3_client, _sqs_client, _parts = _coordinator(
        source_size_bytes=60 * 1024 * 1024 * 1024,
        export_repository=export_repository,
        part_repository=part_repository,
    )
    prepared = await coordinator.prepare(export=export)
    await coordinator.start(export=export, prepared=prepared)

    payload = ExportCopyTaskMessage(
        export_id=export.export_id,
        source_key=export.source_key,
        export_key=prepared.export_key,
        upload_id="worker-upload-id",
        part_number=1,
        start_byte=0,
        end_byte=prepared.copy_part_size_bytes - 1,
    )

    first_failures = await coordinator.process_message_batch(
        messages=[("msg-1", payload)]
    )
    second_failures = await coordinator.process_message_batch(
        messages=[("msg-2", payload)]
    )
    stored = await part_repository.get(
        export_id=export.export_id,
        part_number=1,
    )

    assert first_failures == []
    assert second_failures == []
    assert stored is not None
    assert stored.status.value == "copied"
    assert len(s3_client.part_calls) == 1


@pytest.mark.anyio
async def test_process_message_batch_ignores_stale_upload_id() -> None:
    export_repository = MemoryExportRepository()
    export = _export_record()
    await export_repository.create(export)
    part_repository = MemoryExportCopyPartRepository()
    coordinator, s3_client, _sqs_client, _parts = _coordinator(
        source_size_bytes=60 * 1024 * 1024 * 1024,
        export_repository=export_repository,
        part_repository=part_repository,
    )
    prepared = await coordinator.prepare(export=export)
    await coordinator.start(export=export, prepared=prepared)
    stored = await part_repository.get(
        export_id=export.export_id,
        part_number=1,
    )
    assert stored is not None
    await part_repository.update(
        stored.model_copy(update={"upload_id": "new-worker-upload-id"})
    )

    failures = await coordinator.process_message_batch(
        messages=[
            (
                "msg-1",
                ExportCopyTaskMessage(
                    export_id=export.export_id,
                    source_key=export.source_key,
                    export_key=prepared.export_key,
                    upload_id="worker-upload-id",
                    part_number=1,
                    start_byte=0,
                    end_byte=prepared.copy_part_size_bytes - 1,
                ),
            )
        ]
    )

    refreshed = await part_repository.get(
        export_id=export.export_id,
        part_number=1,
    )
    assert failures == []
    assert refreshed is not None
    assert refreshed.upload_id == "new-worker-upload-id"
    assert refreshed.status.value == "queued"
    assert s3_client.part_calls == []


@pytest.mark.anyio
async def test_process_message_batch_reclaims_expired_copying_part() -> None:
    export_repository = MemoryExportRepository()
    export = _export_record()
    await export_repository.create(export)
    part_repository = MemoryExportCopyPartRepository()
    coordinator, s3_client, _sqs_client, _parts = _coordinator(
        source_size_bytes=60 * 1024 * 1024 * 1024,
        export_repository=export_repository,
        part_repository=part_repository,
    )
    prepared = await coordinator.prepare(export=export)
    await coordinator.start(export=export, prepared=prepared)
    stored = await part_repository.get(
        export_id=export.export_id,
        part_number=1,
    )
    assert stored is not None
    await part_repository.update(
        stored.model_copy(
            update={
                "lease_expires_at_epoch": 1,
                "status": "copying",
            }
        )
    )

    failures = await coordinator.process_message_batch(
        messages=[
            (
                "msg-1",
                ExportCopyTaskMessage(
                    export_id=export.export_id,
                    source_key=export.source_key,
                    export_key=prepared.export_key,
                    upload_id="worker-upload-id",
                    part_number=1,
                    start_byte=0,
                    end_byte=prepared.copy_part_size_bytes - 1,
                ),
            )
        ]
    )

    refreshed = await part_repository.get(
        export_id=export.export_id,
        part_number=1,
    )
    assert failures == []
    assert refreshed is not None
    assert refreshed.status.value == "copied"
    assert len(s3_client.part_calls) == 1


@pytest.mark.anyio
async def test_process_message_batch_stops_when_max_attempts_is_reached() -> (
    None
):
    export_repository = MemoryExportRepository()
    export = _export_record()
    await export_repository.create(export)
    part_repository = MemoryExportCopyPartRepository()
    coordinator, s3_client, _sqs_client, _parts = _coordinator(
        source_size_bytes=60 * 1024 * 1024 * 1024,
        export_repository=export_repository,
        part_repository=part_repository,
    )
    coordinator.max_attempts = 1
    prepared = await coordinator.prepare(export=export)
    await coordinator.start(export=export, prepared=prepared)

    failures = await coordinator.process_message_batch(
        messages=[
            (
                "msg-1",
                ExportCopyTaskMessage(
                    export_id=export.export_id,
                    source_key=export.source_key,
                    export_key=prepared.export_key,
                    upload_id="worker-upload-id",
                    part_number=1,
                    start_byte=0,
                    end_byte=prepared.copy_part_size_bytes - 1,
                ),
            )
        ]
    )

    refreshed = await part_repository.get(
        export_id=export.export_id,
        part_number=1,
    )
    assert failures == []
    assert refreshed is not None
    assert refreshed.status.value == "failed"
    assert refreshed.error == "max_attempts_exceeded"
    assert s3_client.part_calls == []


@pytest.mark.anyio
async def test_start_reuses_existing_worker_upload_id_on_retry() -> None:
    export_repository = MemoryExportRepository()
    export = _export_record()
    await export_repository.create(export)
    coordinator, s3_client, _sqs_client, _parts = _coordinator(
        source_size_bytes=60 * 1024 * 1024 * 1024,
        export_repository=export_repository,
    )
    prepared = await coordinator.prepare(export=export)

    first = await coordinator.start(export=export, prepared=prepared)
    persisted = await export_repository.get(export.export_id)
    assert persisted is not None
    second = await coordinator.start(export=persisted, prepared=prepared)

    assert first == second
    assert len(s3_client.create_calls) == 1


@pytest.mark.anyio
async def test_poll_returns_ready_after_all_parts_complete() -> None:
    export_repository = MemoryExportRepository()
    export = _export_record()
    await export_repository.create(export)
    part_repository = MemoryExportCopyPartRepository()
    coordinator, s3_client, _sqs_client, _parts = _coordinator(
        source_size_bytes=60 * 1024 * 1024 * 1024,
        export_repository=export_repository,
        part_repository=part_repository,
    )
    prepared = await coordinator.prepare(export=export)
    queued = await coordinator.start(export=export, prepared=prepared)
    records = await part_repository.list_for_export(export_id=export.export_id)
    for record in records:
        await part_repository.mark_copied(
            export_id=record.export_id,
            part_number=record.part_number,
            etag=f"etag-{record.part_number}",
        )

    result = await coordinator.poll(
        export=export,
        upload_id=queued.upload_id,
        export_key=queued.export_key,
        download_filename=prepared.download_filename,
    )

    assert result.state == "ready"
    assert result.completed_parts == queued.copy_part_count
    assert len(s3_client.complete_calls) == 1


@pytest.mark.anyio
async def test_poll_treats_completed_upload_retry_as_ready() -> None:
    export_repository = MemoryExportRepository()
    export = _export_record()
    await export_repository.create(export)
    part_repository = MemoryExportCopyPartRepository()
    coordinator, s3_client, _sqs_client, _parts = _coordinator(
        source_size_bytes=60 * 1024 * 1024 * 1024,
        export_repository=export_repository,
        part_repository=part_repository,
    )
    prepared = await coordinator.prepare(export=export)
    queued = await coordinator.start(export=export, prepared=prepared)
    records = await part_repository.list_for_export(export_id=export.export_id)
    for record in records:
        await part_repository.mark_copied(
            export_id=record.export_id,
            part_number=record.part_number,
            etag=f"etag-{record.part_number}",
        )
    s3_client.complete_error = ClientError(
        {"Error": {"Code": "NoSuchUpload"}},
        "CompleteMultipartUpload",
    )
    s3_client.export_object_exists = True

    result = await coordinator.poll(
        export=export,
        upload_id=queued.upload_id,
        export_key=queued.export_key,
        download_filename=prepared.download_filename,
    )

    assert result.state == "ready"
    assert result.output_key == queued.export_key


@pytest.mark.anyio
async def test_poll_aborts_destination_upload_when_export_is_cancelled() -> (
    None
):
    export_repository = MemoryExportRepository()
    export = _export_record()
    await export_repository.create(export)
    part_repository = MemoryExportCopyPartRepository()
    coordinator, s3_client, _sqs_client, _parts = _coordinator(
        source_size_bytes=60 * 1024 * 1024 * 1024,
        export_repository=export_repository,
        part_repository=part_repository,
    )
    prepared = await coordinator.prepare(export=export)
    queued = await coordinator.start(
        export=export,
        prepared=prepared,
    )
    cancelled_export = export.model_copy(
        update={"status": ExportStatus.CANCELLED}
    )

    result = await coordinator.poll(
        export=cancelled_export,
        upload_id=queued.upload_id,
        export_key=queued.export_key,
        download_filename=prepared.download_filename,
    )

    assert result.state == ExportStatus.CANCELLED.value
    assert len(s3_client.abort_calls) == 1
