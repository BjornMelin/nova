"""Scheduled reconciliation for stale transfer session state."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.transfer_usage import TransferUsageWindowRepository
from nova_file_api.upload_sessions import (
    UploadSessionRecord,
    UploadSessionRepository,
    UploadSessionStatus,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class TransferReconciliationConfig:
    """Runtime settings required by the reconciliation service."""

    bucket: str
    upload_prefix: str
    export_prefix: str
    stale_multipart_cleanup_age_seconds: int = 24 * 60 * 60
    session_scan_limit: int = 200


@dataclass(slots=True, frozen=True)
class TransferReconciliationResult:
    """Summary returned after one janitor run."""

    expired_sessions_seen: int = 0
    reconciled_completed_sessions: int = 0
    reconciled_aborted_sessions: int = 0
    aborted_orphan_upload_multipart_uploads: int = 0
    aborted_orphan_export_multipart_uploads: int = 0

    def as_dict(self) -> dict[str, int]:
        """Return a stable machine-readable summary."""
        return {
            "expired_sessions_seen": self.expired_sessions_seen,
            "reconciled_completed_sessions": (
                self.reconciled_completed_sessions
            ),
            "reconciled_aborted_sessions": self.reconciled_aborted_sessions,
            "aborted_orphan_upload_multipart_uploads": (
                self.aborted_orphan_upload_multipart_uploads
            ),
            "aborted_orphan_export_multipart_uploads": (
                self.aborted_orphan_export_multipart_uploads
            ),
        }


class MultipartListingClient(Protocol):
    """Subset of S3 operations used by the janitor."""

    async def abort_multipart_upload(
        self,
        **kwargs: object,
    ) -> Mapping[str, object]:
        """Abort one multipart upload."""

    async def head_object(self, **kwargs: object) -> Mapping[str, object]:
        """Read one object head."""

    async def list_multipart_uploads(
        self,
        **kwargs: object,
    ) -> Mapping[str, object]:
        """List multipart uploads for one prefix."""


@dataclass(slots=True)
class TransferReconciliationService:
    """Reconcile expired upload sessions and stale multipart uploads."""

    config: TransferReconciliationConfig
    s3_client: MultipartListingClient
    upload_session_repository: UploadSessionRepository
    transfer_usage_repository: TransferUsageWindowRepository | None = None

    async def reconcile(
        self,
        *,
        now: datetime | None = None,
    ) -> TransferReconciliationResult:
        """Run one reconciliation pass and return its summary."""
        current_time = _as_utc(now or datetime.now(tz=UTC))
        completed_sessions = 0
        aborted_sessions = 0

        expired_sessions = (
            await self.upload_session_repository.list_expired_multipart(
                now_epoch=int(current_time.timestamp()),
                limit=self.config.session_scan_limit,
            )
        )
        for session in expired_sessions:
            if await self._object_exists(key=session.key):
                await self._update_session(
                    session,
                    status=UploadSessionStatus.COMPLETED,
                    now=current_time,
                )
                await self._release_usage_best_effort(
                    session=session,
                    completed=True,
                )
                completed_sessions += 1
                continue
            await self._abort_multipart_upload(
                key=session.key,
                upload_id=session.upload_id,
            )
            await self._update_session(
                session,
                status=UploadSessionStatus.ABORTED,
                now=current_time,
            )
            await self._release_usage_best_effort(
                session=session,
                completed=False,
            )
            aborted_sessions += 1

        cutoff = current_time - timedelta(
            seconds=self.config.stale_multipart_cleanup_age_seconds
        )
        upload_orphans = await self._abort_stale_orphaned_multipart_uploads(
            prefix=self.config.upload_prefix,
            older_than=cutoff,
        )
        export_orphans = await self._abort_stale_orphaned_multipart_uploads(
            prefix=self.config.export_prefix,
            older_than=cutoff,
        )
        return TransferReconciliationResult(
            expired_sessions_seen=len(expired_sessions),
            reconciled_completed_sessions=completed_sessions,
            reconciled_aborted_sessions=aborted_sessions,
            aborted_orphan_upload_multipart_uploads=upload_orphans,
            aborted_orphan_export_multipart_uploads=export_orphans,
        )

    async def _object_exists(self, *, key: str) -> bool:
        try:
            await self.s3_client.head_object(Bucket=self.config.bucket, Key=key)
        except ClientError as exc:
            if _is_not_found(exc):
                return False
            raise
        except BotoCoreError:
            raise
        return True

    async def _abort_multipart_upload(
        self,
        *,
        key: str,
        upload_id: str | None,
    ) -> None:
        if upload_id is None:
            return
        with suppress(ClientError, BotoCoreError):
            await self.s3_client.abort_multipart_upload(
                Bucket=self.config.bucket,
                Key=key,
                UploadId=upload_id,
            )

    async def _update_session(
        self,
        session: UploadSessionRecord,
        *,
        status: UploadSessionStatus,
        now: datetime,
    ) -> None:
        await self.upload_session_repository.update(
            UploadSessionRecord(
                session_id=session.session_id,
                upload_id=session.upload_id,
                scope_id=session.scope_id,
                key=session.key,
                filename=session.filename,
                size_bytes=session.size_bytes,
                content_type=session.content_type,
                strategy=session.strategy,
                part_size_bytes=session.part_size_bytes,
                policy_id=session.policy_id,
                policy_version=session.policy_version,
                max_concurrency_hint=session.max_concurrency_hint,
                sign_batch_size_hint=session.sign_batch_size_hint,
                accelerate_enabled=session.accelerate_enabled,
                checksum_algorithm=session.checksum_algorithm,
                checksum_mode=session.checksum_mode,
                sign_requests_count=session.sign_requests_count,
                sign_requests_limit=session.sign_requests_limit,
                resumable_until=session.resumable_until,
                resumable_until_epoch=session.resumable_until_epoch,
                status=status,
                request_id=session.request_id,
                created_at=session.created_at,
                last_activity_at=now,
            )
        )

    async def _release_usage_best_effort(
        self,
        *,
        session: UploadSessionRecord,
        completed: bool,
    ) -> None:
        if self.transfer_usage_repository is None:
            return
        try:
            await self.transfer_usage_repository.release_upload(
                scope_id=session.scope_id,
                window_started_at=session.created_at,
                size_bytes=session.size_bytes,
                multipart=True,
                completed=completed,
            )
        except Exception:
            _LOGGER.warning(
                "transfer_reconciliation_usage_release_failed",
                exc_info=True,
                extra={
                    "scope_id": session.scope_id,
                    "upload_id": session.upload_id,
                    "completed": completed,
                },
            )

    async def _abort_stale_orphaned_multipart_uploads(
        self,
        *,
        prefix: str,
        older_than: datetime,
    ) -> int:
        aborted = 0
        key_marker: str | None = None
        upload_id_marker: str | None = None
        while aborted < self.config.session_scan_limit:
            kwargs: dict[str, object] = {
                "Bucket": self.config.bucket,
                "Prefix": prefix,
                "MaxUploads": min(1000, self.config.session_scan_limit),
            }
            if key_marker is not None:
                kwargs["KeyMarker"] = key_marker
            if upload_id_marker is not None:
                kwargs["UploadIdMarker"] = upload_id_marker
            response = await self.s3_client.list_multipart_uploads(**kwargs)
            uploads = cast(list[dict[str, Any]], response.get("Uploads", []))
            for upload in uploads:
                initiated_at = _parse_timestamp(upload.get("Initiated"))
                if initiated_at is None or initiated_at >= older_than:
                    continue
                key = cast(str | None, upload.get("Key"))
                upload_id = cast(str | None, upload.get("UploadId"))
                if key is None or upload_id is None:
                    continue
                if prefix == self.config.upload_prefix:
                    session = (
                        await self.upload_session_repository.get_for_upload_id(
                            upload_id=upload_id
                        )
                    )
                    if session is not None and session.status in {
                        UploadSessionStatus.INITIATED,
                        UploadSessionStatus.ACTIVE,
                    }:
                        continue
                await self._abort_multipart_upload(
                    key=key,
                    upload_id=upload_id,
                )
                aborted += 1
                if aborted >= self.config.session_scan_limit:
                    break
            if (
                not response.get("IsTruncated")
                or aborted >= self.config.session_scan_limit
            ):
                break
            key_marker = cast(str | None, response.get("NextKeyMarker"))
            upload_id_marker = cast(
                str | None,
                response.get("NextUploadIdMarker"),
            )
        return aborted


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _as_utc(parsed)
    return None


def _is_not_found(exc: ClientError) -> bool:
    return str(exc.response.get("Error", {}).get("Code", "")) in {
        "404",
        "NoSuchKey",
        "NotFound",
    }
