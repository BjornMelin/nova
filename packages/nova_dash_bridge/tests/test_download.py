from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import nova_dash_bridge.service as dash_service_module
import nova_file_api.public as public_contract
import pytest
from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_dash_bridge.errors import FileTransferError
from nova_dash_bridge.s3_client import (
    S3Client,
    SupportsCreateS3Client,
)
from nova_dash_bridge.service import (
    AsyncFileTransferService,
    FileTransferService,
)
from nova_file_api.public import (
    InitiateUploadRequest,
    Principal,
    UploadIntrospectionRequest,
)


class _FakeBody:
    def __init__(self, *, chunks: list[bytes] | None = None) -> None:
        self._chunks = list(chunks or [])
        self.closed = False
        self.read_calls = 0

    def read(self, _amt: int | None = None) -> bytes:
        self.read_calls += 1
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def close(self) -> None:
        self.closed = True


class _FakeS3Client:
    def __init__(self, *, response: dict[str, object]) -> None:
        self._response = response

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        del Bucket, Key
        return self._response


class _FakeS3Factory:
    def __init__(self, *, client: _FakeS3Client) -> None:
        self._client = client

    def create(self, _env: FileTransferEnvConfig) -> S3Client:
        return cast("S3Client", self._client)

    @asynccontextmanager
    async def create_async(
        self,
        _env: FileTransferEnvConfig,
    ) -> AsyncIterator[S3Client]:
        yield cast("S3Client", self._client)


class _FakeCoreTransferService:
    def __init__(self, **_: object) -> None:
        self.last_presign_request: (
            public_contract.PresignDownloadRequest | None
        ) = None

    async def introspect_upload(
        self,
        request: object,
        principal: object,
    ) -> public_contract.UploadIntrospectionResponse:
        del request, principal
        return public_contract.UploadIntrospectionResponse(
            bucket="bucket-a",
            key="uploads/scope-1/object.csv",
            upload_id="upload-1",
            part_size_bytes=8,
            parts=[
                public_contract.UploadedPart(
                    part_number=1,
                    etag='"etag-1"',
                )
            ],
        )

    async def presign_download(
        self,
        request: object,
        principal: object,
    ) -> public_contract.PresignDownloadResponse:
        del principal
        self.last_presign_request = cast(
            public_contract.PresignDownloadRequest,
            request,
        )
        return public_contract.PresignDownloadResponse(
            bucket="bucket-a",
            key="exports/scope-1/report.csv",
            url="https://example.invalid/presigned",
            expires_in_seconds=900,
        )


class _SyncOnlyS3Factory:
    def __init__(self, *, client: S3Client) -> None:
        self._client = client

    def create(self, _env: FileTransferEnvConfig) -> S3Client:
        return cast("S3Client", self._client)


def _auth_policy() -> AuthPolicy:
    return AuthPolicy(
        principal_resolver=lambda _: Principal(
            subject="user-1",
            scope_id="scope-1",
        )
    )


def test_file_transfer_service_requires_auth_policy() -> None:
    constructor = cast(Any, FileTransferService)
    with pytest.raises(TypeError, match="auth_policy"):
        constructor(
            env_config=FileTransferEnvConfig.model_validate(
                {
                    "FILE_TRANSFER_ENABLED": True,
                    "FILE_TRANSFER_BUCKET": "bucket-a",
                }
            ),
            upload_policy=UploadPolicy(
                max_upload_bytes=100,
                allowed_extensions={".csv"},
            ),
        )


def _service_with_response(
    *,
    monkeypatch: pytest.MonkeyPatch,
    response: dict[str, object],
    core_service: _FakeCoreTransferService | None = None,
) -> FileTransferService:
    monkeypatch.setattr(
        dash_service_module,
        "build_transfer_service",
        lambda **_: core_service or _FakeCoreTransferService(),
    )
    return FileTransferService(
        env_config=FileTransferEnvConfig.model_validate(
            {
                "FILE_TRANSFER_ENABLED": True,
                "FILE_TRANSFER_BUCKET": "bucket-a",
            }
        ),
        upload_policy=UploadPolicy(
            max_upload_bytes=100,
            allowed_extensions={".csv"},
        ),
        auth_policy=_auth_policy(),
        s3_client_factory=cast(
            "SupportsCreateS3Client",
            _FakeS3Factory(client=_FakeS3Client(response=response)),
        ),
    )


def test_download_closes_stream_when_content_length_exceeds_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _FakeBody()
    service = _service_with_response(
        monkeypatch=monkeypatch,
        response={
            "ContentLength": 11,
            "Body": body,
        },
    )

    with pytest.raises(FileTransferError, match="maximum download size"):
        service.download_object_bytes(
            bucket="bucket-a",
            key="exports/object.csv",
            max_bytes=10,
        )

    assert body.closed is True
    assert body.read_calls == 0


def test_download_supports_sync_only_s3_factory_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=r"create_async\(\)",
    ):
        FileTransferService(
            env_config=FileTransferEnvConfig.model_validate(
                {
                    "FILE_TRANSFER_ENABLED": True,
                    "FILE_TRANSFER_BUCKET": "bucket-a",
                }
            ),
            upload_policy=UploadPolicy(
                max_upload_bytes=100,
                allowed_extensions={".csv"},
            ),
            auth_policy=_auth_policy(),
            s3_client_factory=cast(
                "SupportsCreateS3Client",
                _SyncOnlyS3Factory(
                    client=cast(
                        "S3Client",
                        _FakeS3Client(
                            response={
                                "ContentLength": None,
                                "Body": _FakeBody(),
                            }
                        ),
                    ),
                ),
            ),
        )


def test_download_supports_sync_client_factory() -> None:
    body = _FakeBody(chunks=[b"hello"])
    service = FileTransferService(
        env_config=FileTransferEnvConfig.model_validate(
            {
                "FILE_TRANSFER_ENABLED": True,
                "FILE_TRANSFER_BUCKET": "bucket-a",
            }
        ),
        upload_policy=UploadPolicy(
            max_upload_bytes=100,
            allowed_extensions={".csv"},
        ),
        auth_policy=_auth_policy(),
        s3_client_factory=cast(
            "SupportsCreateS3Client",
            _FakeS3Factory(
                client=cast(
                    "S3Client",
                    _FakeS3Client(
                        response={"ContentLength": None, "Body": body}
                    ),
                )
            ),
        ),
    )

    assert (
        service.download_object_bytes(
            bucket="bucket-a",
            key="exports/object.csv",
            max_bytes=10,
        )
        == b"hello"
    )


def test_download_closes_stream_on_chunked_oversize_early_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = _FakeBody(chunks=[b"abcde", b"fghij", b"k"])
    service = _service_with_response(
        monkeypatch=monkeypatch,
        response={
            "ContentLength": None,
            "Body": body,
        },
    )

    with pytest.raises(FileTransferError, match="maximum download size"):
        service.download_object_bytes(
            bucket="bucket-a",
            key="exports/object.csv",
            max_bytes=10,
        )

    assert body.closed is True
    assert body.read_calls == 3


def test_introspect_upload_maps_core_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service_with_response(
        monkeypatch=monkeypatch,
        response={},
    )

    response = service.introspect_upload(
        UploadIntrospectionRequest(
            key="uploads/scope-1/object.csv",
            upload_id="upload-1",
        ),
        principal=Principal(subject="user-1", scope_id="scope-1"),
    )

    assert response.model_dump() == {
        "bucket": "bucket-a",
        "key": "uploads/scope-1/object.csv",
        "upload_id": "upload-1",
        "part_size_bytes": 8,
        "parts": [{"part_number": 1, "etag": '"etag-1"'}],
    }


def test_presign_download_preserves_explicit_content_disposition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_core = _FakeCoreTransferService()
    service = _service_with_response(
        monkeypatch=monkeypatch,
        response={},
        core_service=fake_core,
    )

    response = service.presign_download(
        public_contract.PresignDownloadRequest(
            key="exports/scope-1/report.csv",
            content_disposition='inline; filename="custom.csv"',
            filename="fallback.csv",
            content_type="text/csv",
        ),
        principal=Principal(subject="user-1", scope_id="scope-1"),
    )

    assert response.url == "https://example.invalid/presigned"
    assert fake_core.last_presign_request is not None
    assert (
        fake_core.last_presign_request.content_disposition
        == 'inline; filename="custom.csv"'
    )
    assert fake_core.last_presign_request.filename == "fallback.csv"
    assert fake_core.last_presign_request.content_type == "text/csv"


@pytest.mark.asyncio
async def test_async_service_rejects_sync_only_s3_factory() -> None:
    service = AsyncFileTransferService(
        env_config=FileTransferEnvConfig.model_validate(
            {
                "FILE_TRANSFER_ENABLED": True,
                "FILE_TRANSFER_BUCKET": "bucket-a",
            }
        ),
        upload_policy=UploadPolicy(
            max_upload_bytes=100,
            allowed_extensions={".csv"},
        ),
        auth_policy=_auth_policy(),
        s3_client_factory=cast(
            "SupportsCreateS3Client",
            _SyncOnlyS3Factory(
                client=cast("S3Client", _FakeS3Client(response={})),
            ),
        ),
    )

    with pytest.raises(
        TypeError,
        match="requires async_s3_client_factory or s3_client_factory "
        "with create_async",
    ):
        await service.initiate_upload(
            InitiateUploadRequest(
                filename="report.csv",
                content_type="text/csv",
                size_bytes=1,
            ),
            Principal(subject="user-1", scope_id="scope-1"),
        )
