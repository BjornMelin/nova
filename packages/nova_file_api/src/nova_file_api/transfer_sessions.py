"""Upload-session lifecycle collaborator for transfer orchestration."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime

from nova_file_api.errors import (
    FileTransferError,
    invalid_request,
    session_store_unavailable,
)
from nova_file_api.models import InitiateUploadRequest, Principal
from nova_file_api.transfer_policy import TransferPolicy
from nova_file_api.upload_sessions import (
    UploadSessionRecord,
    UploadSessionRepository,
    UploadSessionStatus,
    UploadStrategy,
)

_LOGGER = logging.getLogger(__name__)


class UploadSessionLifecycle:
    """Own durable upload-session reads, writes, and state transitions."""

    def __init__(self, repository: UploadSessionRepository) -> None:
        """Initialize session lifecycle with its persistence repository."""
        self._repository = repository

    async def store(self, record: UploadSessionRecord) -> None:
        """Persist one upload-session record or raise canonical API error."""
        try:
            await self._repository.create(record)
        except Exception as exc:
            _LOGGER.exception(
                "upload_session_store_failed",
                extra={
                    "session_id": record.session_id,
                    "upload_id": record.upload_id,
                    "scope_id": record.scope_id,
                },
            )
            raise session_store_unavailable(
                "upload session store is unavailable"
            ) from exc

    async def get(self, *, upload_id: str) -> UploadSessionRecord | None:
        """Return one upload session by S3 upload id."""
        try:
            return await self._repository.get_for_upload_id(upload_id=upload_id)
        except Exception as exc:
            _LOGGER.exception(
                "upload_session_lookup_failed",
                extra={"upload_id": upload_id},
            )
            raise session_store_unavailable(
                "upload session store is unavailable"
            ) from exc

    async def store_best_effort(self, record: UploadSessionRecord) -> None:
        """Persist one session transition without changing caller outcome."""
        try:
            await self.store(record)
        except FileTransferError:
            _LOGGER.warning(
                "upload_session_store_best_effort_failed",
                extra={
                    "session_id": record.session_id,
                    "upload_id": record.upload_id,
                    "scope_id": record.scope_id,
                    "status": record.status.value,
                },
                exc_info=True,
            )

    async def require_for_caller(
        self,
        *,
        upload_id: str,
        scope_id: str,
        key: str,
    ) -> UploadSessionRecord:
        """Return a caller-owned upload session or fail closed."""
        session = await self.get(upload_id=upload_id)
        if session is None:
            raise invalid_request("upload session was not found")
        if session.scope_id != scope_id or session.key != key:
            raise invalid_request("upload session is outside caller scope")
        return session

    async def get_for_caller(
        self,
        *,
        upload_id: str,
        scope_id: str,
        key: str,
    ) -> UploadSessionRecord | None:
        """Return a caller-owned upload session when it exists."""
        session = await self.get(upload_id=upload_id)
        if session is None:
            return None
        if session.scope_id != scope_id or session.key != key:
            raise invalid_request("upload session is outside caller scope")
        return session

    async def touch(
        self,
        *,
        upload_id: str,
        last_activity_at: datetime,
        status: UploadSessionStatus,
        scope_id: str,
        key: str,
    ) -> None:
        """Persist a required upload-session activity transition."""
        session = await self.require_for_caller(
            upload_id=upload_id,
            scope_id=scope_id,
            key=key,
        )
        await self.store(
            replace(
                session,
                status=status,
                last_activity_at=last_activity_at,
            )
        )

    async def touch_if_present(
        self,
        *,
        upload_id: str,
        last_activity_at: datetime,
        status: UploadSessionStatus,
        scope_id: str,
        key: str,
    ) -> None:
        """Best-effort activity transition for optional session state."""
        session = await self.get_for_caller(
            upload_id=upload_id,
            scope_id=scope_id,
            key=key,
        )
        if session is None:
            return
        try:
            await self.store(
                replace(
                    session,
                    status=status,
                    last_activity_at=last_activity_at,
                )
            )
        except FileTransferError:
            _LOGGER.warning(
                "upload_session_touch_best_effort_failed",
                extra={
                    "upload_id": upload_id,
                    "scope_id": scope_id,
                    "key": key,
                    "status": status.value,
                },
                exc_info=True,
            )

    def new_record(
        self,
        *,
        session_id: str,
        upload_id: str | None,
        key: str,
        strategy: UploadStrategy,
        part_size_bytes: int | None,
        created_at: datetime,
        principal: Principal,
        request: InitiateUploadRequest,
        policy: TransferPolicy,
        resumable_until: datetime,
    ) -> UploadSessionRecord:
        """Build the canonical durable upload-session record."""
        return UploadSessionRecord(
            session_id=session_id,
            upload_id=upload_id,
            scope_id=principal.scope_id,
            key=key,
            filename=request.filename,
            size_bytes=request.size_bytes,
            content_type=request.content_type,
            strategy=strategy,
            part_size_bytes=part_size_bytes,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            max_concurrency_hint=policy.max_concurrency_hint,
            sign_batch_size_hint=policy.sign_batch_size_hint,
            accelerate_enabled=policy.accelerate_enabled,
            checksum_algorithm=policy.checksum_algorithm,
            checksum_mode=policy.checksum_mode,
            sign_requests_count=0,
            sign_requests_limit=policy.sign_requests_per_upload_limit,
            resumable_until=resumable_until,
            resumable_until_epoch=int(resumable_until.timestamp()),
            status=UploadSessionStatus.INITIATED,
            request_id=None,
            created_at=created_at,
            last_activity_at=created_at,
        )
