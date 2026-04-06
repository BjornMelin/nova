from __future__ import annotations

import asyncio
import contextlib
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import pytest
from boto3.dynamodb.types import (
    TypeDeserializer,  # type: ignore[import-untyped]
)
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from nova_file_api.config import Settings
from nova_file_api.errors import FileTransferError
from nova_file_api.models import (
    AbortUploadRequest,
    CompletedPart,
    CompleteUploadRequest,
    InitiateUploadRequest,
    PresignDownloadRequest,
    Principal,
    SignPartsRequest,
    UploadedPart,
    UploadIntrospectionRequest,
    UploadStrategy,
)
from nova_file_api.transfer import TransferService
from nova_file_api.transfer_config import transfer_config_from_settings
from nova_file_api.transfer_usage import (
    MemoryTransferUsageRepository,
    TransferUsageWindowRepository,
)
from nova_file_api.upload_sessions import (
    DynamoUploadSessionRepository,
    MemoryUploadSessionRepository,
    UploadSessionRecord,
    UploadSessionRepository,
    UploadSessionStatus,
    _item_to_record,
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "IDEMPOTENCY_ENABLED": False,
        "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
        "FILE_TRANSFER_BUCKET": "test-transfer-bucket",
    }
    values.update(overrides)
    return Settings.model_validate(values)


class _FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.copy_calls: list[dict[str, Any]] = []
        self.multipart_upload_calls: list[dict[str, Any]] = []
        self.upload_part_copy_calls: list[dict[str, Any]] = []
        self.complete_calls: list[dict[str, Any]] = []
        self.abort_calls: list[dict[str, Any]] = []
        self.copy_error: Exception | None = None
        self.head_responses: list[dict[str, Any] | Exception] = []
        self.list_parts_responses: list[dict[str, Any] | Exception] = []
        self.expected_part_markers: list[int | None] = []
        self.multipart_upload_id = "upload-id"
        self.upload_part_copy_wait_event: asyncio.Event | None = None
        self.max_upload_part_copy_in_flight = 0
        self._upload_part_copy_in_flight = 0
        self.presign_wait_event: asyncio.Event | None = None
        self.max_presign_in_flight = 0
        self._presign_in_flight = 0

    async def generate_presigned_url(
        self,
        *,
        ClientMethod: str,
        Params: dict[str, Any],
        ExpiresIn: int,
    ) -> str:
        self._presign_in_flight += 1
        self.max_presign_in_flight = max(
            self.max_presign_in_flight,
            self._presign_in_flight,
        )
        try:
            if self.presign_wait_event is not None:
                await self.presign_wait_event.wait()
            self.calls.append(
                {
                    "ClientMethod": ClientMethod,
                    "Params": Params,
                    "ExpiresIn": ExpiresIn,
                }
            )
            return "https://example.local/presigned"
        finally:
            self._presign_in_flight -= 1

    async def head_object(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        if self.head_responses:
            item = self.head_responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return {}

    async def copy_object(self, **kwargs: Any) -> dict[str, Any]:
        self.copy_calls.append(kwargs)
        if self.copy_error is not None:
            raise self.copy_error
        return {}

    async def create_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        self.multipart_upload_calls.append(kwargs)
        return {"UploadId": self.multipart_upload_id}

    async def upload_part_copy(self, **kwargs: Any) -> dict[str, Any]:
        self.upload_part_copy_calls.append(kwargs)
        self._upload_part_copy_in_flight += 1
        self.max_upload_part_copy_in_flight = max(
            self.max_upload_part_copy_in_flight,
            self._upload_part_copy_in_flight,
        )
        try:
            if self.upload_part_copy_wait_event is not None:
                await self.upload_part_copy_wait_event.wait()
            if self.copy_error is not None:
                raise self.copy_error
            return {
                "CopyPartResult": {"ETag": f"etag-{kwargs['PartNumber']}"},
            }
        finally:
            self._upload_part_copy_in_flight -= 1

    async def list_parts(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"list_parts": kwargs})
        if self.expected_part_markers:
            expected_marker = self.expected_part_markers.pop(0)
            observed_marker = kwargs.get("PartNumberMarker")
            if observed_marker != expected_marker:
                raise AssertionError(
                    "expected PartNumberMarker "
                    f"{expected_marker!r} but received {observed_marker!r}"
                )
        if self.list_parts_responses:
            item = self.list_parts_responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return {"Parts": [], "IsTruncated": False}

    async def complete_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        self.complete_calls.append(kwargs)
        return {"ETag": "etag", "VersionId": "version"}

    async def abort_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        self.abort_calls.append(kwargs)
        return {}


class _RecordingTransferUsageRepository(MemoryTransferUsageRepository):
    """Tracks ``release_upload`` calls for cancellation tests."""

    def __init__(self) -> None:
        super().__init__()
        self.release_upload_calls = 0

    async def release_upload(
        self,
        *,
        scope_id: str,
        window_started_at: datetime,
        size_bytes: int,
        multipart: bool,
        completed: bool,
    ) -> None:
        self.release_upload_calls += 1
        await super().release_upload(
            scope_id=scope_id,
            window_started_at=window_started_at,
            size_bytes=size_bytes,
            multipart=multipart,
            completed=completed,
        )


class _FailingUploadSessionRepository(MemoryUploadSessionRepository):
    def __init__(self) -> None:
        super().__init__()
        self.fail_create = False

    async def create(self, record: UploadSessionRecord) -> None:
        if self.fail_create:
            raise RuntimeError("session store unavailable")
        await super().create(record)


class _LaggingUploadSessionTable:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self.get_item_calls: list[dict[str, Any]] = []
        self.put_item_calls: list[dict[str, Any]] = []
        self.scan_calls: list[dict[str, Any]] = []
        self.transact_write_calls: list[dict[str, Any]] = []
        self.fail_transact_write = False
        self.meta = type(
            "_Meta",
            (),
            {"client": _LaggingUploadSessionClient(self)},
        )()

    async def put_item(self, **kwargs: object) -> dict[str, object]:
        item = deepcopy(cast(dict[str, Any], kwargs["Item"]))
        session_id = item["session_id"]
        assert isinstance(session_id, str)
        self.put_item_calls.append(dict(kwargs))
        self._items[session_id] = item
        return {}

    async def get_item(self, **kwargs: object) -> dict[str, object]:
        self.get_item_calls.append(deepcopy(dict(kwargs)))
        key = cast(dict[str, Any], kwargs["Key"])
        session_id = key["session_id"]
        assert isinstance(session_id, str)
        item = self._items.get(session_id)
        return {"Item": deepcopy(item)} if item is not None else {}

    async def scan(self, **kwargs: object) -> dict[str, object]:
        self.scan_calls.append(deepcopy(dict(kwargs)))
        filter_expression = cast(str, kwargs["FilterExpression"])
        names = cast(dict[str, str], kwargs["ExpressionAttributeNames"])
        values = cast(dict[str, Any], kwargs["ExpressionAttributeValues"])
        now_epoch = values[":now_epoch"]
        assert isinstance(now_epoch, int)
        allowed_record_types: set[str | None] | None = None
        record_type_name = names.get("#record_type")
        if (
            record_type_name == "record_type"
            and "#record_type = :session_record" in filter_expression
        ):
            allowed_record_types = {values[":session_record"]}
            if "attribute_not_exists(#record_type)" in filter_expression:
                allowed_record_types.add(None)
        allowed_statuses = {
            values[":initiated"],
            values[":active"],
        }
        multipart_value = values[":multipart"]
        items = [
            deepcopy(item)
            for item in self._items.values()
            if (
                allowed_record_types is None
                or item.get("record_type") in allowed_record_types
            )
            and item.get("strategy") == multipart_value
            and item.get("status") in allowed_statuses
            and int(item["resumable_until_epoch"]) <= now_epoch
        ]
        limit = kwargs.get("Limit")
        if isinstance(limit, int):
            items = items[:limit]
        return {"Items": items}


_TYPE_DESERIALIZER = TypeDeserializer()


class _LaggingUploadSessionClient:
    def __init__(self, table: _LaggingUploadSessionTable) -> None:
        self._table = table

    async def transact_write_items(self, **kwargs: object) -> dict[str, object]:
        self._table.transact_write_calls.append(deepcopy(dict(kwargs)))
        if self._table.fail_transact_write:
            raise RuntimeError("transaction write failed")
        for request in cast(list[dict[str, Any]], kwargs["TransactItems"]):
            if "Put" in request:
                put = cast(dict[str, Any], request["Put"])
                item = _deserialize_item(cast(dict[str, Any], put["Item"]))
                session_id = item["session_id"]
                assert isinstance(session_id, str)
                self._table._items[session_id] = item
                continue
            delete = cast(dict[str, Any], request["Delete"])
            key = _deserialize_item(cast(dict[str, Any], delete["Key"]))
            session_id = key["session_id"]
            assert isinstance(session_id, str)
            self._table._items.pop(session_id, None)
        return {}


def _deserialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _TYPE_DESERIALIZER.deserialize(value)
        for key, value in item.items()
    }


class _LaggingUploadSessionResource:
    def __init__(self, table: _LaggingUploadSessionTable) -> None:
        self.table = table

    def Table(self, table_name: str) -> _LaggingUploadSessionTable:
        assert table_name == "upload-sessions"
        return self.table


class _TableWithoutTransactionClient:
    async def put_item(self, **kwargs: object) -> dict[str, object]:
        del kwargs
        return {}

    async def get_item(self, **kwargs: object) -> dict[str, object]:
        del kwargs
        return {}

    async def scan(self, **kwargs: object) -> dict[str, object]:
        del kwargs
        return {}


class _ResourceWithoutTransactionClient:
    def Table(self, table_name: str) -> _TableWithoutTransactionClient:
        assert table_name == "upload-sessions"
        return _TableWithoutTransactionClient()


def _upload_session_record(
    *,
    key: str = "uploads/scope-1/report.csv",
    upload_id: str = "upload-1",
    created_at: datetime | None = None,
    resumable_until: datetime | None = None,
) -> UploadSessionRecord:
    now = datetime.now(tz=UTC) if created_at is None else created_at
    session_resumable_until = (
        (now + timedelta(hours=1)).replace(microsecond=0)
        if resumable_until is None
        else resumable_until
    )
    return UploadSessionRecord(
        session_id="session-1",
        upload_id=upload_id,
        scope_id="scope-1",
        key=key,
        filename="report.csv",
        size_bytes=1024,
        content_type="text/csv",
        strategy=UploadStrategy.MULTIPART,
        part_size_bytes=256 * 1024 * 1024,
        policy_id="default",
        policy_version="2026-04-03",
        max_concurrency_hint=4,
        sign_batch_size_hint=32,
        accelerate_enabled=False,
        checksum_algorithm=None,
        checksum_mode="none",
        sign_requests_count=0,
        sign_requests_limit=None,
        resumable_until=session_resumable_until,
        resumable_until_epoch=int(session_resumable_until.timestamp()),
        status=UploadSessionStatus.INITIATED,
        request_id="request-1",
        created_at=now,
        last_activity_at=now,
    )


def _lagging_upload_session_repository(
    table: _LaggingUploadSessionTable | None = None,
) -> tuple[DynamoUploadSessionRepository, _LaggingUploadSessionTable]:
    resolved_table = _LaggingUploadSessionTable() if table is None else table
    return (
        DynamoUploadSessionRepository(
            table_name="upload-sessions",
            dynamodb_resource=_LaggingUploadSessionResource(resolved_table),
        ),
        resolved_table,
    )


@pytest.fixture
def _service() -> tuple[TransferService, _FakeS3Client]:
    fake_s3 = _FakeS3Client()
    service = _transfer_service(settings=_settings(), s3_client=fake_s3)
    return service, fake_s3


def _transfer_service(
    *,
    settings: Settings,
    s3_client: _FakeS3Client,
    upload_session_repository: UploadSessionRepository | None = None,
    transfer_usage_repository: TransferUsageWindowRepository | None = None,
) -> TransferService:
    return TransferService(
        config=transfer_config_from_settings(settings),
        s3_client=s3_client,
        upload_session_repository=(
            upload_session_repository or MemoryUploadSessionRepository()
        ),
        transfer_usage_repository=transfer_usage_repository,
    )


def _principal() -> Principal:
    return Principal(subject="user-1", scope_id="scope-1")


def _copy_upload_error_case(
    *,
    error: Exception,
) -> tuple[TransferService, Settings, _FakeS3Client]:
    settings = _settings()
    fake_s3 = _FakeS3Client()
    service = _transfer_service(settings=settings, s3_client=fake_s3)
    fake_s3.head_responses = [
        {"LastModified": "2024-01-01T00:00:00Z", "ContentLength": 42},
    ]
    fake_s3.copy_error = error
    return service, settings, fake_s3


@pytest.mark.anyio
async def test_presign_download_preserves_explicit_content_disposition(
    _service: tuple[TransferService, _FakeS3Client],
) -> None:
    service, fake_s3 = _service

    await service.presign_download(
        request=PresignDownloadRequest(
            key="uploads/scope-1/file.csv",
            content_disposition='inline; filename="custom.csv"',
            filename="fallback.csv",
            content_type=None,
        ),
        principal=_principal(),
    )

    params = fake_s3.calls[0]["Params"]
    assert (
        params["ResponseContentDisposition"] == 'inline; filename="custom.csv"'
    )
    assert "ResponseContentType" not in params


@pytest.mark.anyio
async def test_presign_download_uses_filename_fallback_when_disposition_missing(
    _service: tuple[TransferService, _FakeS3Client],
) -> None:
    service, fake_s3 = _service

    await service.presign_download(
        request=PresignDownloadRequest(
            key="uploads/scope-1/file.csv",
            content_disposition=None,
            filename="../report final.csv",
            content_type=None,
        ),
        principal=_principal(),
    )

    params = fake_s3.calls[0]["Params"]
    assert (
        params["ResponseContentDisposition"]
        == 'attachment; filename="report final.csv"'
    )


@pytest.mark.anyio
async def test_single_upload_required_checksum_signs_put_object_header() -> (
    None
):
    settings = _settings(
        FILE_TRANSFER_CHECKSUM_ALGORITHM="SHA256",
        FILE_TRANSFER_CHECKSUM_MODE="required",
        FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES=1024 * 1024 * 1024,
    )
    fake_s3 = _FakeS3Client()
    service = _transfer_service(settings=settings, s3_client=fake_s3)

    response = await service.initiate_upload(
        request=InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=1024,
            checksum_value="sha256-base64-value",
        ),
        principal=_principal(),
    )

    assert response.strategy == UploadStrategy.SINGLE
    assert response.checksum_mode == "required"
    params = fake_s3.calls[0]["Params"]
    assert params["ChecksumSHA256"] == "sha256-base64-value"


@pytest.mark.anyio
async def test_initiate_upload_returns_policy_hints_and_persists_session() -> (
    None
):
    settings = _settings(
        FILE_TRANSFER_POLICY_ID="giant-tier",
        FILE_TRANSFER_POLICY_VERSION="2026-04-03",
        FILE_TRANSFER_RESUMABLE_WINDOW_SECONDS=86_400,
        FILE_TRANSFER_TARGET_UPLOAD_PART_COUNT=2000,
        FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES=2 * 1024 * 1024 * 1024,
        FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY=8,
    )
    fake_s3 = _FakeS3Client()
    repository = MemoryUploadSessionRepository()
    service = _transfer_service(
        settings=settings,
        s3_client=fake_s3,
        upload_session_repository=repository,
    )

    response = await service.initiate_upload(
        request=InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=500 * 1024 * 1024 * 1024,
        ),
        principal=_principal(),
    )

    assert response.strategy.value == "multipart"
    assert response.policy_id == "giant-tier"
    assert response.policy_version == "2026-04-03"
    assert (
        response.max_concurrency_hint == settings.file_transfer_max_concurrency
    )
    assert response.sign_batch_size_hint == 64
    assert response.accelerate_enabled is False
    assert response.checksum_algorithm is None
    assert response.part_size_bytes == 256 * 1024 * 1024
    assert response.resumable_until > datetime.now(tz=UTC)
    assert response.upload_id == fake_s3.multipart_upload_id
    assert response.session_id

    stored = repository._records_by_session_id[response.session_id]
    assert stored.status == UploadSessionStatus.INITIATED
    assert stored.upload_id == fake_s3.multipart_upload_id
    assert stored.part_size_bytes == 256 * 1024 * 1024
    assert stored.policy_id == "giant-tier"
    assert stored.checksum_mode == "none"


@pytest.mark.anyio
async def test_introspect_upload_uses_persisted_session_part_size() -> None:
    settings = _settings()
    fake_s3 = _FakeS3Client()
    repository = MemoryUploadSessionRepository()
    service = _transfer_service(
        settings=settings,
        s3_client=fake_s3,
        upload_session_repository=repository,
    )

    initiated = await service.initiate_upload(
        request=InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=500 * 1024 * 1024 * 1024,
        ),
        principal=_principal(),
    )
    fake_s3.list_parts_responses = [
        {
            "Parts": [
                {"PartNumber": 1, "ETag": '"etag-1"', "Size": 1},
            ],
            "IsTruncated": False,
        }
    ]

    response = await service.introspect_upload(
        request=UploadIntrospectionRequest(
            key=initiated.key,
            upload_id=initiated.upload_id or "",
        ),
        principal=_principal(),
    )

    assert response.part_size_bytes == 256 * 1024 * 1024
    stored = repository._records_by_session_id[initiated.session_id]
    assert stored.status == UploadSessionStatus.ACTIVE
    assert stored.last_activity_at.tzinfo is not None


@pytest.mark.anyio
async def test_sign_parts_requires_existing_upload_session() -> None:
    settings = _settings()
    fake_s3 = _FakeS3Client()
    service = _transfer_service(settings=settings, s3_client=fake_s3)

    with pytest.raises(FileTransferError) as exc_info:
        await service.sign_parts(
            request=SignPartsRequest(
                key="uploads/scope-1/report.csv",
                upload_id="missing-upload",
                part_numbers=[1],
            ),
            principal=_principal(),
        )

    assert exc_info.value.code == "invalid_request"
    assert str(exc_info.value) == "upload session was not found"


def test_transfer_service_requires_repository_when_sessions_enabled() -> None:
    settings = _settings(FILE_TRANSFER_UPLOAD_SESSIONS_TABLE="sessions-table")

    with pytest.raises(ValueError, match="dynamodb_resource must be provided"):
        TransferService(
            config=transfer_config_from_settings(settings),
            s3_client=_FakeS3Client(),
        )


def test_upload_session_record_parses_decimal_part_size() -> None:
    now = datetime.now(tz=UTC)

    record = _item_to_record(
        {
            "session_id": "session-1",
            "upload_id": "upload-1",
            "scope_id": "scope-1",
            "key": "uploads/scope-1/report.csv",
            "filename": "report.csv",
            "size_bytes": Decimal("1024"),
            "content_type": "text/csv",
            "strategy": "multipart",
            "part_size_bytes": Decimal(str(256 * 1024 * 1024)),
            "policy_id": "default",
            "policy_version": "2026-04-03",
            "max_concurrency_hint": Decimal("4"),
            "sign_batch_size_hint": Decimal("32"),
            "accelerate_enabled": False,
            "checksum_algorithm": None,
            "resumable_until": now.isoformat(),
            "resumable_until_epoch": Decimal("123456789"),
            "status": "initiated",
            "request_id": "request-1",
            "created_at": now.isoformat(),
            "last_activity_at": now.isoformat(),
        }
    )

    assert record.part_size_bytes == 256 * 1024 * 1024
    assert record.max_concurrency_hint == 4
    assert record.sign_batch_size_hint == 32


@pytest.mark.parametrize(
    ("copy_error", "expected_code", "expected_status", "expected_message"),
    [
        pytest.param(
            ClientError(
                error_response={"Error": {"Code": "NoSuchKey"}},
                operation_name="CopyObject",
            ),
            "invalid_request",
            422,
            "source upload object not found",
            id="no-such-key-is-invalid-request",
        ),
        pytest.param(
            BotoCoreError(),
            "upstream_s3_error",
            502,
            "failed to copy upload object to export key",
            id="botocore-error-maps-upstream",
        ),
        pytest.param(
            ClientError(
                error_response={"Error": {"Code": "AccessDenied"}},
                operation_name="CopyObject",
            ),
            "upstream_s3_error",
            502,
            "failed to copy upload object to export key",
            id="client-error-maps-upstream",
        ),
    ],
)
@pytest.mark.anyio
async def test_copy_upload_to_export_error_mapping(
    copy_error: Exception,
    expected_code: str,
    expected_status: int,
    expected_message: str,
) -> None:
    """Verify copy failures map to the expected public error envelope.

    Args:
        copy_error: Exception raised by the fake copy implementation.
        expected_code: Expected FileTransferError.code value.
        expected_status: Expected FileTransferError.status_code value.
        expected_message: Expected rendered error message text.

    Returns:
        None.
    """
    service, settings, _fake_s3 = _copy_upload_error_case(error=copy_error)

    with pytest.raises(FileTransferError) as exc_info:
        await service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket or "",
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            export_id="job-1",
            filename="source.csv",
        )

    assert exc_info.value.code == expected_code
    assert exc_info.value.status_code == expected_status
    assert str(exc_info.value) == expected_message


@pytest.mark.anyio
async def test_introspect_upload_lists_parts_across_pages() -> None:
    settings = _settings()
    fake_s3 = _FakeS3Client()
    service = _transfer_service(settings=settings, s3_client=fake_s3)
    fake_s3.expected_part_markers = [None, 1]
    fake_s3.list_parts_responses = [
        {
            "Parts": [
                {"PartNumber": 1, "ETag": '"etag-1"', "Size": 8},
            ],
            "IsTruncated": True,
            "NextPartNumberMarker": 1,
        },
        {
            "Parts": [
                {"PartNumber": 2, "ETag": '"etag-2"', "Size": 9},
            ],
            "IsTruncated": False,
        },
    ]

    response = await service.introspect_upload(
        request=UploadIntrospectionRequest(
            key="uploads/scope-1/file.csv",
            upload_id="upload-1",
        ),
        principal=_principal(),
    )

    assert response.part_size_bytes == 8
    assert [part.model_dump() for part in response.parts] == [
        {"part_number": 1, "etag": '"etag-1"'},
        {"part_number": 2, "etag": '"etag-2"'},
    ]


@pytest.mark.anyio
async def test_complete_upload_verifies_listed_parts_and_object_size() -> None:
    settings = _settings()
    fake_s3 = _FakeS3Client()
    service = _transfer_service(settings=settings, s3_client=fake_s3)
    fake_s3.list_parts_responses = [
        {
            "Parts": [
                {"PartNumber": 1, "ETag": '"etag-1"', "Size": 3},
                {"PartNumber": 2, "ETag": '"etag-2"', "Size": 4},
            ],
            "IsTruncated": False,
        }
    ]
    fake_s3.head_responses = [{"ContentLength": 7}]

    response = await service.complete_upload(
        request=CompleteUploadRequest(
            key="uploads/scope-1/file.csv",
            upload_id="upload-1",
            parts=[
                CompletedPart(part_number=2, etag='"etag-2"'),
                CompletedPart(part_number=1, etag='"etag-1"'),
            ],
        ),
        principal=_principal(),
    )

    assert response.etag == "etag"
    assert fake_s3.complete_calls[0]["MultipartUpload"]["Parts"] == [
        {"ETag": '"etag-1"', "PartNumber": 1},
        {"ETag": '"etag-2"', "PartNumber": 2},
    ]


@pytest.mark.anyio
async def test_complete_upload_succeeds_when_post_check_fails() -> None:
    settings = _settings()
    fake_s3 = _FakeS3Client()
    service = _transfer_service(settings=settings, s3_client=fake_s3)
    fake_s3.list_parts_responses = [
        {
            "Parts": [
                {"PartNumber": 1, "ETag": '"etag-1"', "Size": 3},
                {"PartNumber": 2, "ETag": '"etag-2"', "Size": 4},
            ],
            "IsTruncated": False,
        }
    ]
    fake_s3.head_responses = [BotoCoreError()]

    response = await service.complete_upload(
        request=CompleteUploadRequest(
            key="uploads/scope-1/file.csv",
            upload_id="upload-1",
            parts=[
                CompletedPart(part_number=1, etag='"etag-1"'),
                CompletedPart(part_number=2, etag='"etag-2"'),
            ],
        ),
        principal=_principal(),
    )

    assert response.etag == "etag"
    assert fake_s3.complete_calls[0]["UploadId"] == "upload-1"


@pytest.mark.anyio
async def test_complete_upload_tolerates_session_store_failure() -> None:
    settings = _settings()
    fake_s3 = _FakeS3Client()
    repository = _FailingUploadSessionRepository()
    service = _transfer_service(
        settings=settings,
        s3_client=fake_s3,
        upload_session_repository=repository,
    )
    initiated = await service.initiate_upload(
        request=InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=500 * 1024 * 1024 * 1024,
        ),
        principal=_principal(),
    )
    repository.fail_create = False
    stored = repository._records_by_session_id[initiated.session_id]
    fake_s3.list_parts_responses = [
        {
            "Parts": [{"PartNumber": 1, "ETag": '"etag-1"', "Size": 3}],
            "IsTruncated": False,
        }
    ]
    fake_s3.head_responses = [{"ContentLength": 3}]
    repository.fail_create = True

    response = await service.complete_upload(
        request=CompleteUploadRequest(
            key=stored.key,
            upload_id=initiated.upload_id or "",
            parts=[CompletedPart(part_number=1, etag='"etag-1"')],
        ),
        principal=_principal(),
    )

    assert response.etag == "etag"


@pytest.mark.anyio
async def test_complete_upload_rejects_missing_part() -> None:
    settings = _settings()
    fake_s3 = _FakeS3Client()
    service = _transfer_service(settings=settings, s3_client=fake_s3)
    fake_s3.list_parts_responses = [
        {
            "Parts": [{"PartNumber": 1, "ETag": '"etag-1"', "Size": 3}],
            "IsTruncated": False,
        }
    ]

    with pytest.raises(FileTransferError) as exc_info:
        await service.complete_upload(
            request=CompleteUploadRequest(
                key="uploads/scope-1/file.csv",
                upload_id="upload-1",
                parts=[CompletedPart(part_number=2, etag='"etag-2"')],
            ),
            principal=_principal(),
        )

    assert exc_info.value.code == "invalid_request"
    assert str(exc_info.value) == "multipart upload part is missing"


@pytest.mark.anyio
async def test_complete_upload_rejects_duplicate_part_numbers() -> None:
    settings = _settings()
    fake_s3 = _FakeS3Client()
    service = _transfer_service(settings=settings, s3_client=fake_s3)
    fake_s3.list_parts_responses = [
        {
            "Parts": [{"PartNumber": 1, "ETag": '"etag-1"', "Size": 3}],
            "IsTruncated": False,
        }
    ]

    with pytest.raises(FileTransferError) as exc_info:
        await service.complete_upload(
            request=CompleteUploadRequest(
                key="uploads/scope-1/file.csv",
                upload_id="upload-1",
                parts=[
                    CompletedPart(part_number=1, etag='"etag-1"'),
                    CompletedPart(part_number=1, etag='"etag-1"'),
                ],
            ),
            principal=_principal(),
        )

    assert exc_info.value.code == "invalid_request"
    assert str(exc_info.value) == "multipart upload part numbers must be unique"
    assert exc_info.value.details == {"part_numbers": [1]}
    assert fake_s3.complete_calls == []


def test_complete_upload_request_requires_contiguous_checksum_parts() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "parts must be consecutive and start at 1 when "
            "checksum_sha256 is provided"
        ),
    ):
        CompleteUploadRequest(
            key="uploads/scope-1/file.csv",
            upload_id="upload-1",
            parts=[
                CompletedPart(
                    part_number=1,
                    etag='"etag-1"',
                    checksum_sha256="checksum-1",
                ),
                CompletedPart(
                    part_number=3,
                    etag='"etag-3"',
                    checksum_sha256="checksum-3",
                ),
            ],
        )


@pytest.mark.anyio
async def test_abort_upload_checks_session_scope_before_update() -> None:
    settings = _settings()
    fake_s3 = _FakeS3Client()
    repository = MemoryUploadSessionRepository()
    service = _transfer_service(
        settings=settings,
        s3_client=fake_s3,
        upload_session_repository=repository,
    )
    now = datetime.now(tz=UTC)
    stored = UploadSessionRecord(
        session_id="session-1",
        upload_id="upload-1",
        scope_id="other-scope",
        key="uploads/scope-1/report.csv",
        filename="report.csv",
        size_bytes=1024,
        content_type="text/csv",
        strategy=UploadStrategy.MULTIPART,
        part_size_bytes=256 * 1024 * 1024,
        policy_id="default",
        policy_version="2026-04-03",
        max_concurrency_hint=4,
        sign_batch_size_hint=32,
        accelerate_enabled=False,
        checksum_algorithm=None,
        checksum_mode="none",
        sign_requests_count=0,
        sign_requests_limit=None,
        resumable_until=now,
        resumable_until_epoch=int(now.timestamp()) + 3600,
        status=UploadSessionStatus.INITIATED,
        request_id="request-1",
        created_at=now,
        last_activity_at=now,
    )
    await repository.create(stored)

    with pytest.raises(FileTransferError) as exc_info:
        await service.abort_upload(
            request=AbortUploadRequest(
                key="uploads/scope-1/report.csv",
                upload_id="upload-1",
            ),
            principal=_principal(),
        )

    assert exc_info.value.code == "invalid_request"
    assert str(exc_info.value) == "upload session is outside caller scope"
    assert repository._records_by_session_id[stored.session_id] == stored


@pytest.mark.anyio
async def test_sign_parts_includes_checksum_header_when_required() -> None:
    settings = _settings(
        FILE_TRANSFER_CHECKSUM_ALGORITHM="SHA256",
        FILE_TRANSFER_CHECKSUM_MODE="required",
        FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES=5 * 1024 * 1024,
    )
    fake_s3 = _FakeS3Client()
    service = _transfer_service(settings=settings, s3_client=fake_s3)
    initiated = await service.initiate_upload(
        request=InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=6 * 1024 * 1024,
            checksum_preference="strict",
        ),
        principal=_principal(),
    )

    await service.sign_parts(
        request=SignPartsRequest(
            key=initiated.key,
            upload_id=initiated.upload_id or "",
            part_numbers=[1],
            checksums_sha256={1: "part-checksum"},
        ),
        principal=_principal(),
    )

    assert fake_s3.calls[-1]["Params"]["ChecksumSHA256"] == "part-checksum"


@pytest.mark.anyio
async def test_initiate_upload_releases_quota_on_cancel_during_presign() -> (
    None
):
    """Quota release runs on cancel (shielded), not only on plain failure."""
    settings = _settings(
        # Single-part path awaits presign; multipart initiate does not presign
        # in this handler.
        FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES=500 * 1024 * 1024 * 1024,
    )
    fake_s3 = _FakeS3Client()
    fake_s3.presign_wait_event = asyncio.Event()
    usage = _RecordingTransferUsageRepository()
    service = _transfer_service(
        settings=settings,
        s3_client=fake_s3,
        transfer_usage_repository=usage,
    )
    task = asyncio.create_task(
        service.initiate_upload(
            request=InitiateUploadRequest(
                filename="report.csv",
                content_type="text/csv",
                size_bytes=6 * 1024 * 1024,
            ),
            principal=_principal(),
        )
    )
    for _ in range(200):
        if fake_s3._presign_in_flight > 0:
            break
        await asyncio.sleep(0)
    assert fake_s3._presign_in_flight > 0
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert usage.release_upload_calls == 1


@pytest.mark.anyio
async def test_sign_parts_presigns_multiple_parts_concurrently() -> None:
    settings = _settings(
        FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES=5 * 1024 * 1024,
        FILE_TRANSFER_SIGN_BATCH_SIZE_HINT=10,
    )
    fake_s3 = _FakeS3Client()
    fake_s3.presign_wait_event = asyncio.Event()
    service = _transfer_service(settings=settings, s3_client=fake_s3)
    initiated = await service.initiate_upload(
        request=InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=6 * 1024 * 1024,
        ),
        principal=_principal(),
    )

    sign_task = asyncio.create_task(
        service.sign_parts(
            request=SignPartsRequest(
                key=initiated.key,
                upload_id=initiated.upload_id or "",
                part_numbers=[1, 2, 3],
            ),
            principal=_principal(),
        )
    )
    try:
        for _ in range(100):
            if fake_s3.max_presign_in_flight >= 3:
                break
            await asyncio.sleep(0)

        assert fake_s3.max_presign_in_flight == 3
        fake_s3.presign_wait_event.set()
        response = await sign_task
    finally:
        if (
            fake_s3.presign_wait_event is not None
            and not fake_s3.presign_wait_event.is_set()
        ):
            fake_s3.presign_wait_event.set()
        if not sign_task.done():
            sign_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sign_task

    presign_calls = [
        c for c in fake_s3.calls if c.get("ClientMethod") == "upload_part"
    ]
    assert len(presign_calls) == 3
    assert set(response.urls.keys()) == {1, 2, 3}


@pytest.mark.anyio
async def test_abort_upload_tolerates_session_store_failure() -> None:
    settings = _settings()
    fake_s3 = _FakeS3Client()
    repository = _FailingUploadSessionRepository()
    service = _transfer_service(
        settings=settings,
        s3_client=fake_s3,
        upload_session_repository=repository,
    )
    initiated = await service.initiate_upload(
        request=InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=500 * 1024 * 1024 * 1024,
        ),
        principal=_principal(),
    )
    repository.fail_create = False
    stored = repository._records_by_session_id[initiated.session_id]
    repository.fail_create = True

    response = await service.abort_upload(
        request=AbortUploadRequest(
            key=stored.key,
            upload_id=initiated.upload_id or "",
        ),
        principal=_principal(),
    )

    assert response.ok is True


@pytest.mark.anyio
async def test_upload_session_repository_ignores_expired_records() -> None:
    repository = MemoryUploadSessionRepository()
    now = datetime.now(tz=UTC)
    expired = UploadSessionRecord(
        session_id="session-1",
        upload_id="upload-1",
        scope_id="scope-1",
        key="uploads/scope-1/report.csv",
        filename="report.csv",
        size_bytes=1024,
        content_type="text/csv",
        strategy=UploadStrategy.MULTIPART,
        part_size_bytes=256 * 1024 * 1024,
        policy_id="default",
        policy_version="2026-04-03",
        max_concurrency_hint=4,
        sign_batch_size_hint=32,
        accelerate_enabled=False,
        checksum_algorithm=None,
        checksum_mode="none",
        sign_requests_count=0,
        sign_requests_limit=None,
        resumable_until=now,
        resumable_until_epoch=int(now.timestamp()) - 1,
        status=UploadSessionStatus.INITIATED,
        request_id="request-1",
        created_at=now,
        last_activity_at=now,
    )

    await repository.create(expired)

    assert await repository.get_for_upload_id(upload_id="upload-1") is None


@pytest.mark.anyio
async def test_dynamo_upload_repository_uses_strong_upload_alias_lookup() -> (
    None
):
    repository, table = _lagging_upload_session_repository()
    record = _upload_session_record()

    await repository.create(record)

    loaded = await repository.get_for_upload_id(upload_id="upload-1")

    assert loaded == record
    assert table.get_item_calls[-1]["ConsistentRead"] is True
    assert len(table.transact_write_calls) == 1


@pytest.mark.anyio
async def test_dynamo_upload_repository_create_is_atomic() -> None:
    repository, table = _lagging_upload_session_repository()
    table.fail_transact_write = True

    with pytest.raises(RuntimeError, match="transaction write failed"):
        await repository.create(_upload_session_record())

    assert table._items == {}


@pytest.mark.anyio
async def test_dynamo_upload_repository_update_is_atomic() -> None:
    repository, table = _lagging_upload_session_repository()
    original = _upload_session_record()
    await repository.create(original)
    table.fail_transact_write = True
    updated = replace(
        original,
        status=UploadSessionStatus.ACTIVE,
        sign_requests_count=2,
        last_activity_at=original.last_activity_at + timedelta(minutes=5),
    )

    with pytest.raises(RuntimeError, match="transaction write failed"):
        await repository.update(updated)

    assert await repository.get_for_upload_id(upload_id="upload-1") == original


@pytest.mark.anyio
async def test_memory_upload_repository_update_removes_stale_alias() -> None:
    repository = MemoryUploadSessionRepository()
    original = _upload_session_record(upload_id="upload-1")
    await repository.create(original)
    updated = replace(original, upload_id="upload-2")

    await repository.update(updated)

    assert await repository.get_for_upload_id(upload_id="upload-1") is None
    assert await repository.get_for_upload_id(upload_id="upload-2") == updated


@pytest.mark.anyio
async def test_dynamo_upload_repository_update_removes_stale_alias() -> None:
    repository, _table = _lagging_upload_session_repository()
    original = _upload_session_record(upload_id="upload-1")
    await repository.create(original)
    updated = replace(original, upload_id="upload-2")

    await repository.update(updated)

    assert await repository.get_for_upload_id(upload_id="upload-1") is None
    assert await repository.get_for_upload_id(upload_id="upload-2") == updated


@pytest.mark.anyio
async def test_dynamo_upload_repository_requires_transaction_client() -> None:
    repository = DynamoUploadSessionRepository(
        table_name="upload-sessions",
        dynamodb_resource=_ResourceWithoutTransactionClient(),
    )

    with pytest.raises(
        TypeError,
        match=r"transact_write_items",
    ):
        await repository.create(_upload_session_record())


@pytest.mark.anyio
async def test_dynamo_upload_repository_scan_ignores_upload_alias_rows() -> (
    None
):
    repository, table = _lagging_upload_session_repository()
    now = datetime.now(tz=UTC)
    record = _upload_session_record(
        created_at=now,
        resumable_until=now,
    )

    await repository.create(record)

    expired = await repository.list_expired_multipart(
        now_epoch=int(now.timestamp()),
        limit=10,
    )

    assert expired == [record]
    assert "#record_type = :session_record" in cast(
        str, table.scan_calls[-1]["FilterExpression"]
    )


@pytest.mark.anyio
async def test_immediate_sign_parts_uses_authoritative_upload_lookup() -> None:
    settings = _settings(
        FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES=5 * 1024 * 1024,
    )
    repository, table = _lagging_upload_session_repository()
    fake_s3 = _FakeS3Client()
    service = _transfer_service(
        settings=settings,
        s3_client=fake_s3,
        upload_session_repository=repository,
    )

    initiated = await service.initiate_upload(
        request=InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=6 * 1024 * 1024,
        ),
        principal=_principal(),
    )

    response = await service.sign_parts(
        request=SignPartsRequest(
            key=initiated.key,
            upload_id=initiated.upload_id or "",
            part_numbers=[1, 2],
        ),
        principal=_principal(),
    )

    assert set(response.urls) == {1, 2}
    assert table.get_item_calls[-1]["ConsistentRead"] is True


@pytest.mark.anyio
async def test_immediate_introspect_uses_authoritative_upload_lookup() -> None:
    settings = _settings(
        FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES=5 * 1024 * 1024,
    )
    repository, _table = _lagging_upload_session_repository()
    fake_s3 = _FakeS3Client()
    fake_s3.list_parts_responses = [
        {
            "Parts": [
                {"PartNumber": 1, "ETag": '"etag-1"', "Size": 1},
            ],
            "IsTruncated": False,
        }
    ]
    service = _transfer_service(
        settings=settings,
        s3_client=fake_s3,
        upload_session_repository=repository,
    )

    initiated = await service.initiate_upload(
        request=InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=6 * 1024 * 1024,
        ),
        principal=_principal(),
    )

    response = await service.introspect_upload(
        request=UploadIntrospectionRequest(
            key=initiated.key,
            upload_id=initiated.upload_id or "",
        ),
        principal=_principal(),
    )
    stored = await repository.get_for_upload_id(
        upload_id=initiated.upload_id or ""
    )

    assert response.parts == [UploadedPart(part_number=1, etag='"etag-1"')]
    assert stored is not None
    assert stored.status == UploadSessionStatus.ACTIVE


@pytest.mark.anyio
async def test_immediate_complete_updates_authoritative_upload_lookup() -> None:
    settings = _settings(
        FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES=5 * 1024 * 1024,
    )
    repository, _table = _lagging_upload_session_repository()
    fake_s3 = _FakeS3Client()
    fake_s3.list_parts_responses = [
        {
            "Parts": [{"PartNumber": 1, "ETag": '"etag-1"', "Size": 3}],
            "IsTruncated": False,
        }
    ]
    fake_s3.head_responses = [{"ContentLength": 3}]
    service = _transfer_service(
        settings=settings,
        s3_client=fake_s3,
        upload_session_repository=repository,
    )

    initiated = await service.initiate_upload(
        request=InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=6 * 1024 * 1024,
        ),
        principal=_principal(),
    )

    response = await service.complete_upload(
        request=CompleteUploadRequest(
            key=initiated.key,
            upload_id=initiated.upload_id or "",
            parts=[CompletedPart(part_number=1, etag='"etag-1"')],
        ),
        principal=_principal(),
    )
    stored = await repository.get_for_upload_id(
        upload_id=initiated.upload_id or ""
    )

    assert response.etag == "etag"
    assert stored is not None
    assert stored.status == UploadSessionStatus.COMPLETED


@pytest.mark.anyio
async def test_immediate_abort_updates_authoritative_upload_lookup() -> None:
    settings = _settings(
        FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES=5 * 1024 * 1024,
    )
    repository, _table = _lagging_upload_session_repository()
    fake_s3 = _FakeS3Client()
    service = _transfer_service(
        settings=settings,
        s3_client=fake_s3,
        upload_session_repository=repository,
    )

    initiated = await service.initiate_upload(
        request=InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=6 * 1024 * 1024,
        ),
        principal=_principal(),
    )

    response = await service.abort_upload(
        request=AbortUploadRequest(
            key=initiated.key,
            upload_id=initiated.upload_id or "",
        ),
        principal=_principal(),
    )
    stored = await repository.get_for_upload_id(
        upload_id=initiated.upload_id or ""
    )

    assert response.ok is True
    assert stored is not None
    assert stored.status == UploadSessionStatus.ABORTED


def test_transfer_config_preferred_part_size_remains_lower_bound() -> None:
    settings = _settings(
        FILE_TRANSFER_PART_SIZE_BYTES=128 * 1024 * 1024,
        FILE_TRANSFER_TARGET_UPLOAD_PART_COUNT=2000,
    )

    config = transfer_config_from_settings(settings)

    assert config.upload_part_size_bytes(size_bytes=500 * 1024 * 1024) == (
        128 * 1024 * 1024
    )


@pytest.mark.anyio
async def test_copy_upload_to_export_uses_multipart_copy_above_5_gb() -> None:
    settings = _settings(
        FILE_TRANSFER_PART_SIZE_BYTES=128 * 1024 * 1024,
        FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES=2 * 1024 * 1024 * 1024,
    )
    fake_s3 = _FakeS3Client()
    service = _transfer_service(settings=settings, s3_client=fake_s3)
    fake_s3.head_responses = [
        {
            "ContentLength": 5_000_000_001,
            "ContentType": "text/csv",
            "Metadata": {"source": "unit-test"},
        }
    ]

    result = await service.copy_upload_to_export(
        source_bucket=settings.file_transfer_bucket or "",
        source_key="uploads/scope-1/source.csv",
        scope_id="scope-1",
        export_id="job-1",
        filename="source.csv",
    )

    assert result.export_key.endswith("/source.csv")
    assert fake_s3.copy_calls == []
    assert fake_s3.multipart_upload_calls == [
        {
            "Bucket": settings.file_transfer_bucket or "",
            "Key": result.export_key,
            "ContentType": "text/csv",
            "Metadata": {"source": "unit-test"},
        }
    ]
    expected_content_length = 5_000_000_001
    part_size_bytes = settings.file_transfer_export_copy_part_size_bytes
    expected_part_count = (
        expected_content_length + part_size_bytes - 1
    ) // part_size_bytes
    assert len(fake_s3.upload_part_copy_calls) == expected_part_count
    previous_end_byte = -1
    for expected_part_number, call in enumerate(
        fake_s3.upload_part_copy_calls, start=1
    ):
        assert call["PartNumber"] == expected_part_number
        copy_source_range = call["CopySourceRange"]
        assert copy_source_range.startswith("bytes=")
        range_without_prefix = copy_source_range.removeprefix("bytes=")
        start_str, end_str = range_without_prefix.split("-", 1)
        start_byte = int(start_str)
        end_byte = int(end_str)
        assert start_byte == previous_end_byte + 1
        if expected_part_number < expected_part_count:
            assert end_byte == (start_byte + part_size_bytes - 1)
        else:
            assert end_byte == expected_content_length - 1
        previous_end_byte = end_byte
    assert fake_s3.complete_calls[-1]["UploadId"] == fake_s3.multipart_upload_id


@pytest.mark.anyio
async def test_copy_upload_to_export_aborts_failed_multipart_copy() -> None:
    settings = _settings(
        FILE_TRANSFER_PART_SIZE_BYTES=128 * 1024 * 1024,
    )
    fake_s3 = _FakeS3Client()
    fake_s3.copy_error = ClientError(
        error_response={"Error": {"Code": "AccessDenied"}},
        operation_name="UploadPartCopy",
    )
    service = _transfer_service(settings=settings, s3_client=fake_s3)
    fake_s3.head_responses = [{"ContentLength": 5_000_000_001}]

    with pytest.raises(FileTransferError) as exc_info:
        await service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket or "",
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            export_id="job-1",
            filename="source.csv",
        )

    assert exc_info.value.code == "upstream_s3_error"
    assert len(fake_s3.abort_calls) == 1


@pytest.mark.anyio
async def test_copy_upload_to_export_limits_multipart_copy_concurrency() -> (
    None
):
    settings = _settings(
        FILE_TRANSFER_PART_SIZE_BYTES=2_000_000_000,
        FILE_TRANSFER_MAX_CONCURRENCY=2,
    )
    fake_s3 = _FakeS3Client()
    fake_s3.upload_part_copy_wait_event = asyncio.Event()
    fake_s3.head_responses = [{"ContentLength": 5_000_000_001}]
    service = _transfer_service(settings=settings, s3_client=fake_s3)

    copy_task = asyncio.create_task(
        service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket or "",
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            export_id="job-1",
            filename="source.csv",
        )
    )
    try:
        for _ in range(100):
            if fake_s3.max_upload_part_copy_in_flight >= 2:
                break
            await asyncio.sleep(0)

        assert fake_s3.max_upload_part_copy_in_flight == 2
        fake_s3.upload_part_copy_wait_event.set()
        await copy_task
        assert len(fake_s3.upload_part_copy_calls) == 3
    finally:
        if not fake_s3.upload_part_copy_wait_event.is_set():
            fake_s3.upload_part_copy_wait_event.set()
        if not copy_task.done():
            copy_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await copy_task


@pytest.mark.anyio
async def test_large_copy_missing_source_is_invalid() -> None:
    settings = _settings(
        FILE_TRANSFER_PART_SIZE_BYTES=128 * 1024 * 1024,
    )
    fake_s3 = _FakeS3Client()
    fake_s3.copy_error = ClientError(
        error_response={"Error": {"Code": "NoSuchKey"}},
        operation_name="UploadPartCopy",
    )
    service = _transfer_service(settings=settings, s3_client=fake_s3)
    fake_s3.head_responses = [{"ContentLength": 5_000_000_001}]

    with pytest.raises(FileTransferError) as exc_info:
        await service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket or "",
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            export_id="job-1",
            filename="source.csv",
        )

    assert exc_info.value.code == "invalid_request"
    assert exc_info.value.status_code == 422
    assert str(exc_info.value) == "source upload object not found"
    assert len(fake_s3.abort_calls) == 1
