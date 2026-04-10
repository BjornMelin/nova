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
        """Create a quota manager backed by the given usage repository.

        Args:
            repository: Persistent or in-memory usage counters.

        Returns:
            None
        """
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
        """Reserve quota for one upload initiation.

        Args:
            scope_id: Caller scope owning the upload.
            created_at: Timestamp used for daily window accounting.
            size_bytes: Declared upload size for ingress budgeting.
            multipart: Whether this reservation counts as an active multipart.
            policy: Resolved limits (active multipart cap, daily budget).

        Returns:
            None

        Raises:
            too_many_requests: When ``TransferQuotaExceeded`` is raised by the
                repository (active multipart or daily ingress limits).
        """
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
        """Release quota after rollback or terminal upload, swallowing errors.

        Args:
            scope_id: Caller scope that held the reservation.
            created_at: Timestamp aligned with the original reservation window.
            size_bytes: Size passed to the matching ``reserve_upload`` call.
            multipart: Whether the upload was multipart.
            completed: Whether the upload finished successfully (affects byte
                accounting).

        Returns:
            None

        Raises:
            None: Failures are logged and not propagated.
        """
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
        """Record one sign-parts call against the scope hourly usage window.

        Args:
            scope_id: Caller scope performing the sign request.
            sign_requested_at: Time used to select the hourly counter window.
            hourly_sign_request_limit: Optional **scope hourly** cap enforced by
                the repository (not the per-upload sign limit). ``None``
                disables hourly enforcement while still incrementing counters.

        Returns:
            None

        Raises:
            too_many_requests: When the hourly sign budget is exhausted.
        """
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
