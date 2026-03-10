from __future__ import annotations

import nova_dash_bridge.service as dash_service_module
import pytest
from nova_dash_bridge.config import FileTransferEnvConfig, UploadPolicy
from nova_dash_bridge.errors import FileTransferError
from nova_dash_bridge.service import FileTransferService


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

    def create(self, _env: FileTransferEnvConfig) -> _FakeS3Client:
        return self._client


class _FakeCoreTransferService:
    """Satisfy bridge constructor dependency for download-focused tests."""

    def __init__(
        self, *, settings: object, s3_client: object | None = None
    ) -> None:
        del settings, s3_client


def _service_with_response(
    *,
    monkeypatch: pytest.MonkeyPatch,
    response: dict[str, object],
) -> FileTransferService:
    monkeypatch.setattr(
        dash_service_module,
        "TransferService",
        _FakeCoreTransferService,
    )
    return FileTransferService(
        env_config=FileTransferEnvConfig(
            enabled=True,
            bucket="bucket-a",
        ),
        upload_policy=UploadPolicy(
            max_upload_bytes=100,
            allowed_extensions={".csv"},
        ),
        s3_client_factory=_FakeS3Factory(
            client=_FakeS3Client(response=response)
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
