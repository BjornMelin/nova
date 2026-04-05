from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from nova_file_api.transfer_usage import (
    DynamoTransferUsageRepository,
    MemoryTransferUsageRepository,
    TransferQuotaExceeded,
)


class _CapturingUsageTable:
    def __init__(self) -> None:
        self.update_calls: list[dict[str, Any]] = []

    async def get_item(self, **_: object) -> dict[str, object]:
        return {}

    async def update_item(self, **kwargs: object) -> dict[str, object]:
        self.update_calls.append(dict(kwargs))
        return {}


class _CapturingUsageResource:
    def __init__(self) -> None:
        self.table = _CapturingUsageTable()

    def Table(self, table_name: str) -> _CapturingUsageTable:
        assert table_name == "transfer-usage"
        return self.table


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


@pytest.mark.anyio
async def test_dynamo_reserve_upload_uses_remaining_budget_condition() -> None:
    resource = _CapturingUsageResource()
    repository = DynamoTransferUsageRepository(
        table_name="transfer-usage",
        dynamodb_resource=resource,
    )
    now = datetime(2026, 4, 3, 12, 0, tzinfo=UTC)

    await repository.reserve_upload(
        scope_id="scope-1",
        window_started_at=now,
        size_bytes=60,
        multipart=False,
        active_multipart_limit=None,
        daily_ingress_budget_bytes=100,
    )

    update = resource.table.update_calls[-1]
    assert update["ConditionExpression"] == (
        "attribute_not_exists(bytes_initiated) "
        "OR bytes_initiated <= :remaining_bytes"
    )
    assert update["ExpressionAttributeValues"][":remaining_bytes"] == 40


@pytest.mark.anyio
async def test_dynamo_rejects_oversize_daily_request() -> None:
    repository = DynamoTransferUsageRepository(
        table_name="transfer-usage",
        dynamodb_resource=_CapturingUsageResource(),
    )
    now = datetime(2026, 4, 3, 12, 0, tzinfo=UTC)

    with pytest.raises(TransferQuotaExceeded) as exc_info:
        await repository.reserve_upload(
            scope_id="scope-1",
            window_started_at=now,
            size_bytes=101,
            multipart=False,
            active_multipart_limit=None,
            daily_ingress_budget_bytes=100,
        )

    assert exc_info.value.reason == "daily_ingress_budget_bytes"


@pytest.mark.anyio
async def test_dynamo_active_window_sets_ttl_for_self_healing() -> None:
    resource = _CapturingUsageResource()
    repository = DynamoTransferUsageRepository(
        table_name="transfer-usage",
        dynamodb_resource=resource,
    )
    now = datetime(2026, 4, 3, 12, 0, tzinfo=UTC)

    await repository.reserve_upload(
        scope_id="scope-1",
        window_started_at=now,
        size_bytes=1024,
        multipart=True,
        active_multipart_limit=2,
        daily_ingress_budget_bytes=None,
    )

    update = resource.table.update_calls[-1]
    assert update["Key"] == {
        "scope_id": "scope-1",
        "window_key": "active",
    }
    updated_at = datetime.fromisoformat(
        update["ExpressionAttributeValues"][":updated_at"]
    )
    assert update["ExpressionAttributeValues"][":expires_at"] == int(
        updated_at.timestamp() + 7 * 24 * 60 * 60
    )


@pytest.mark.anyio
async def test_as_utc_normalizes_aware_datetimes() -> None:
    from nova_file_api.transfer_usage import _as_utc

    aware = datetime(2026, 4, 3, 6, 0, tzinfo=timezone(timedelta(hours=-6)))

    assert _as_utc(aware) == datetime(2026, 4, 3, 12, 0, tzinfo=UTC)
