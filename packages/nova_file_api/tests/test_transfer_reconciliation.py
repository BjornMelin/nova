from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nova_file_api.models import UploadStrategy
from nova_runtime_support.transfer_reconciliation import (
    TransferReconciliationConfig,
    TransferReconciliationService,
)
from nova_runtime_support.transfer_usage import MemoryTransferUsageRepository
from nova_runtime_support.upload_sessions import (
    MemoryUploadSessionRepository,
    UploadSessionRecord,
    UploadSessionStatus,
)


class _StubS3Client:
    def __init__(self) -> None:
        self.objects: set[str] = set()
        self.aborts: list[dict[str, str]] = []
        self.uploads: list[dict[str, object]] = []

    async def head_object(self, **kwargs: object) -> dict[str, object]:
        key = str(kwargs["Key"])
        if key not in self.objects:
            raise _not_found()
        return {"ContentLength": 1024}

    async def abort_multipart_upload(
        self,
        **kwargs: object,
    ) -> dict[str, object]:
        self.aborts.append(
            {
                "Key": str(kwargs["Key"]),
                "UploadId": str(kwargs["UploadId"]),
            }
        )
        return {}

    async def list_multipart_uploads(
        self,
        **_: object,
    ) -> dict[str, object]:
        return {"Uploads": self.uploads, "IsTruncated": False}


def _not_found() -> Exception:
    from botocore.exceptions import ClientError

    return ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "missing"}},
        "HeadObject",
    )


def _record(
    *,
    key: str,
    upload_id: str,
    created_at: datetime,
) -> UploadSessionRecord:
    return UploadSessionRecord(
        session_id=f"session-{upload_id}",
        upload_id=upload_id,
        scope_id="scope-1",
        key=key,
        filename="file.bin",
        size_bytes=1024,
        content_type="application/octet-stream",
        strategy=UploadStrategy.MULTIPART,
        part_size_bytes=128 * 1024 * 1024,
        policy_id="default",
        policy_version="2026-04-03",
        max_concurrency_hint=4,
        sign_batch_size_hint=32,
        accelerate_enabled=False,
        checksum_algorithm=None,
        sign_requests_count=0,
        sign_requests_limit=512,
        resumable_until=created_at,
        resumable_until_epoch=int(created_at.timestamp()),
        status=UploadSessionStatus.ACTIVE,
        request_id=None,
        created_at=created_at,
        last_activity_at=created_at,
    )


@pytest.mark.anyio
async def test_reconcile_marks_completed_sessions_and_releases_usage() -> None:
    now = datetime.now(tz=UTC)
    repository = MemoryUploadSessionRepository()
    usage = MemoryTransferUsageRepository()
    session = _record(
        key="uploads/scope-1/object.bin",
        upload_id="upload-1",
        created_at=now - timedelta(hours=2),
    )
    await repository.create(session)
    await usage.reserve_upload(
        scope_id=session.scope_id,
        window_started_at=session.created_at,
        size_bytes=session.size_bytes,
        multipart=True,
        active_multipart_limit=10,
        daily_ingress_budget_bytes=10_000,
    )
    s3_client = _StubS3Client()
    s3_client.objects.add(session.key)
    service = TransferReconciliationService(
        config=TransferReconciliationConfig(
            bucket="bucket",
            upload_prefix="uploads/",
            export_prefix="exports/",
        ),
        s3_client=s3_client,
        upload_session_repository=repository,
        transfer_usage_repository=usage,
    )

    result = await service.reconcile(now=now)
    stored = repository._records_by_session_id[session.session_id]

    assert result.expired_sessions_seen == 1
    assert result.reconciled_completed_sessions == 1
    assert stored is not None
    assert stored.status == UploadSessionStatus.COMPLETED


@pytest.mark.anyio
async def test_reconcile_aborts_missing_sessions_and_orphan_uploads() -> None:
    now = datetime.now(tz=UTC)
    repository = MemoryUploadSessionRepository()
    session = _record(
        key="uploads/scope-1/object.bin",
        upload_id="upload-2",
        created_at=now - timedelta(days=2),
    )
    await repository.create(session)
    s3_client = _StubS3Client()
    s3_client.uploads = [
        {
            "Key": "exports/scope-1/export-1/file.csv",
            "UploadId": "orphan-export-upload",
            "Initiated": now - timedelta(days=2),
        }
    ]
    service = TransferReconciliationService(
        config=TransferReconciliationConfig(
            bucket="bucket",
            upload_prefix="uploads/",
            export_prefix="exports/",
        ),
        s3_client=s3_client,
        upload_session_repository=repository,
    )

    result = await service.reconcile(now=now)
    stored = repository._records_by_session_id[session.session_id]

    assert result.reconciled_aborted_sessions == 1
    assert result.aborted_orphan_export_multipart_uploads == 1
    assert stored is not None
    assert stored.status == UploadSessionStatus.ABORTED
    assert {abort["UploadId"] for abort in s3_client.aborts} == {
        "upload-2",
        "orphan-export-upload",
    }
