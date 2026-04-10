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
    """Own durable upload-session reads, writes, and state transitions.

    Persistence failures from ``store`` / ``get`` are mapped to
    ``session_store_unavailable`` unless documented otherwise on a specific
    method.
    """

    def __init__(self, repository: UploadSessionRepository) -> None:
        """Create a lifecycle helper bound to one repository.

        Args:
            repository: Upload session persistence backend.

        Returns:
            None
        """
        self._repository = repository

    async def store(self, record: UploadSessionRecord) -> None:
        """Persist one upload session, using create or update as appropriate.

        Args:
            record: Session row to write. New rows without an upload id use
                ``create``; otherwise the implementation loads by upload id and
                chooses ``create`` vs ``update``.

        Returns:
            None

        Raises:
            FileTransferError: ``session_store_unavailable`` when persistence
                fails unexpectedly.
        """
        try:
            if record.upload_id is None:
                await self._repository.create(record)
            else:
                existing = await self._repository.get_for_upload_id(
                    upload_id=record.upload_id,
                )
                if existing is None:
                    await self._repository.create(record)
                else:
                    await self._repository.update(record)
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
        """Return one upload session by S3 multipart upload id.

        Args:
            upload_id: S3 ``UploadId`` for the session.

        Returns:
            The session when present, otherwise ``None``.

        Raises:
            FileTransferError: ``session_store_unavailable`` on storage errors.
        """
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
        """Persist one session transition; log ``FileTransferError`` only.

        Args:
            record: Session row to write.

        Returns:
            None

        Raises:
            None: Does not re-raise ``FileTransferError`` from ``store``.
        """
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
        """Return a caller-owned upload session or fail closed.

        Args:
            upload_id: S3 multipart upload id.
            scope_id: Expected caller scope id.
            key: Expected object key.

        Returns:
            The verified session record.

        Raises:
            invalid_request: Missing session or scope/key mismatch.
            FileTransferError: Storage errors from ``get``.
        """
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
        """Return a caller-owned upload session when it exists.

        Args:
            upload_id: S3 multipart upload id.
            scope_id: Expected caller scope id.
            key: Expected object key.

        Returns:
            The session, or ``None`` if missing.

        Raises:
            invalid_request: Scope/key mismatch for an existing session.
            FileTransferError: Storage errors from ``get``.
        """
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
        """Persist a required upload-session activity transition.

        Args:
            upload_id: Session to update.
            last_activity_at: New activity timestamp.
            status: New session status.
            scope_id: Caller scope id.
            key: Object key.

        Returns:
            None

        Raises:
            invalid_request: Session missing or scope/key mismatch.
            FileTransferError: Storage errors from ``require_for_caller`` or
                ``store``.
        """
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
        """Best-effort activity transition when the session may be absent.

        Args:
            upload_id: Session to update when found.
            last_activity_at: New activity timestamp.
            status: New session status.
            scope_id: Caller scope id.
            key: Object key.

        Returns:
            None

        Raises:
            invalid_request: Scope/key mismatch when a session exists.

        ``FileTransferError`` from ``store`` is logged and not propagated.
        """
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
        """Build the canonical durable upload-session record for initiate.

        Args:
            session_id: New session identifier.
            upload_id: S3 upload id when known; ``None`` before multipart
                create.
            key: Object key for the upload.
            strategy: Simple vs multipart strategy.
            part_size_bytes: Declared part size for multipart sessions.
            created_at: Creation timestamp.
            principal: Caller identity and scope.
            request: Initiate request payload (size, name, content type, ...).
            policy: Resolved transfer policy for limits and checksum mode.
            resumable_until: Expiry for resumable session metadata.

        Returns:
            ``UploadSessionRecord`` ready for ``store`` (initially initiated).
        """
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
