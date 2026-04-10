"""Transfer quota coordination helpers."""

from __future__ import annotations

import logging
from datetime import datetime

from nova_file_api.errors import too_many_requests
from nova_file_api.transfer_policy import TransferPolicy
from nova_file_api.transfer_usage import (
    TransferQuotaExceeded,
    TransferUsageWindowRepository,
)

_LOGGER = logging.getLogger(__name__)


class TransferQuotaManager:
    """Own transfer usage-window reservation and release behavior."""

    def __init__(self, repository: TransferUsageWindowRepository) -> None:
        """Initialize quota coordination with its usage repository."""
        self._repository = repository

    async def reserve_upload(
        self,
        *,
        scope_id: str,
        created_at: datetime,
        size_bytes: int,
        multipart: bool,
        policy: TransferPolicy,
    ) -> None:
        """Reserve quota for one upload initiation."""
        try:
            await self._repository.reserve_upload(
                scope_id=scope_id,
                window_started_at=created_at,
                size_bytes=size_bytes,
                multipart=multipart,
                active_multipart_limit=policy.active_multipart_upload_limit,
                daily_ingress_budget_bytes=policy.daily_ingress_budget_bytes,
            )
        except TransferQuotaExceeded as exc:
            raise too_many_requests(
                "transfer quota exceeded for the current scope",
                details={"reason": exc.reason, **exc.details},
            ) from exc

    async def release_upload_best_effort(
        self,
        *,
        scope_id: str,
        created_at: datetime,
        size_bytes: int,
        multipart: bool,
        completed: bool,
    ) -> None:
        """Release quota, logging failures without masking caller outcomes."""
        try:
            await self._repository.release_upload(
                scope_id=scope_id,
                window_started_at=created_at,
                size_bytes=size_bytes,
                multipart=multipart,
                completed=completed,
            )
        except Exception:
            _LOGGER.warning(
                "transfer_usage_release_failed",
                extra={
                    "scope_id": scope_id,
                    "size_bytes": size_bytes,
                    "multipart": multipart,
                    "completed": completed,
                },
                exc_info=True,
            )

    async def record_sign_request(
        self,
        *,
        scope_id: str,
        sign_requested_at: datetime,
        hourly_sign_request_limit: int | None,
    ) -> None:
        """Record a multipart part-signing request for quota enforcement."""
        try:
            await self._repository.record_sign_request(
                scope_id=scope_id,
                window_started_at=sign_requested_at,
                hourly_sign_request_limit=hourly_sign_request_limit,
            )
        except TransferQuotaExceeded as exc:
            raise too_many_requests(
                "sign-parts quota exceeded for the current scope",
                details={"reason": exc.reason, **exc.details},
            ) from exc
