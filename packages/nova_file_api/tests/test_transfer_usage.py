from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nova_runtime_support.transfer_usage import (
    MemoryTransferUsageRepository,
    TransferQuotaExceeded,
)


@pytest.mark.anyio
async def test_reserve_upload_enforces_active_multipart_limit() -> None:
    repository = MemoryTransferUsageRepository()
    now = datetime.now(tz=UTC)

    await repository.reserve_upload(
        scope_id="scope-1",
        window_started_at=now,
        size_bytes=1024,
        multipart=True,
        active_multipart_limit=1,
        daily_ingress_budget_bytes=None,
    )

    with pytest.raises(TransferQuotaExceeded) as exc_info:
        await repository.reserve_upload(
            scope_id="scope-1",
            window_started_at=now,
            size_bytes=1024,
            multipart=True,
            active_multipart_limit=1,
            daily_ingress_budget_bytes=None,
        )

    assert exc_info.value.reason == "active_multipart_limit"


@pytest.mark.anyio
async def test_reserve_upload_enforces_daily_ingress_budget() -> None:
    repository = MemoryTransferUsageRepository()
    now = datetime.now(tz=UTC)

    await repository.reserve_upload(
        scope_id="scope-1",
        window_started_at=now,
        size_bytes=50,
        multipart=False,
        active_multipart_limit=None,
        daily_ingress_budget_bytes=100,
    )

    with pytest.raises(TransferQuotaExceeded) as exc_info:
        await repository.reserve_upload(
            scope_id="scope-1",
            window_started_at=now,
            size_bytes=60,
            multipart=False,
            active_multipart_limit=None,
            daily_ingress_budget_bytes=100,
        )

    assert exc_info.value.reason == "daily_ingress_budget_bytes"


@pytest.mark.anyio
async def test_record_sign_request_enforces_hourly_limit() -> None:
    repository = MemoryTransferUsageRepository()
    now = datetime.now(tz=UTC)

    await repository.record_sign_request(
        scope_id="scope-1",
        window_started_at=now,
        hourly_sign_request_limit=1,
    )

    with pytest.raises(TransferQuotaExceeded) as exc_info:
        await repository.record_sign_request(
            scope_id="scope-1",
            window_started_at=now,
            hourly_sign_request_limit=1,
        )

    assert exc_info.value.reason == "hourly_sign_request_limit"
