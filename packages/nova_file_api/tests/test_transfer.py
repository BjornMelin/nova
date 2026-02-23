from __future__ import annotations

from typing import Any

import pytest
from nova_file_api.config import Settings
from nova_file_api.models import PresignDownloadRequest, Principal
from nova_file_api.transfer import TransferService


class _FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate_presigned_url(
        self,
        *,
        ClientMethod: str,
        Params: dict[str, Any],
        ExpiresIn: int,
    ) -> str:
        self.calls.append(
            {
                "ClientMethod": ClientMethod,
                "Params": Params,
                "ExpiresIn": ExpiresIn,
            }
        )
        return "https://example.local/presigned"


@pytest.fixture
def _service(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TransferService, _FakeS3Client]:
    fake_s3 = _FakeS3Client()

    def _fake_build_s3_client(*, settings: Settings) -> _FakeS3Client:
        del settings
        return fake_s3

    monkeypatch.setattr(
        "nova_file_api.transfer._build_s3_client", _fake_build_s3_client
    )
    service = TransferService(settings=Settings())
    return service, fake_s3


def _principal() -> Principal:
    return Principal(subject="user-1", scope_id="scope-1")


def test_presign_download_preserves_explicit_content_disposition(
    _service: tuple[TransferService, _FakeS3Client],
) -> None:
    service, fake_s3 = _service

    service.presign_download(
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


def test_presign_download_uses_filename_fallback_when_disposition_missing(
    _service: tuple[TransferService, _FakeS3Client],
) -> None:
    service, fake_s3 = _service

    service.presign_download(
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
        == 'attachment; filename="reportfinal.csv"'
    )
