from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import BotoCoreError, ClientError
from nova_file_api.config import Settings
from nova_file_api.errors import FileTransferError
from nova_file_api.models import PresignDownloadRequest, Principal
from nova_file_api.transfer import TransferService


class _FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.copy_calls: list[dict[str, Any]] = []
        self.copy_error: Exception | None = None
        self.head_responses: list[dict[str, Any] | Exception] = []

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

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        if self.head_responses:
            item = self.head_responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return {}

    def copy_object(self, **kwargs: Any) -> dict[str, Any]:
        self.copy_calls.append(kwargs)
        if self.copy_error is not None:
            raise self.copy_error
        return {}


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


def test_copy_upload_to_export_toctou_source_missing_is_invalid_request() -> (
    None
):
    settings = Settings()
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=settings, s3_client=fake_s3)

    fake_s3.head_responses = [
        {"LastModified": "2024-01-01T00:00:00Z"},
    ]
    fake_s3.copy_error = ClientError(
        error_response={"Error": {"Code": "NoSuchKey"}},
        operation_name="CopyObject",
    )

    with pytest.raises(FileTransferError) as exc_info:
        service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket,
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            job_id="job-1",
            filename="source.csv",
        )

    assert exc_info.value.code == "invalid_request"
    assert exc_info.value.status_code == 422
    assert str(exc_info.value) == "source upload object not found"


def test_copy_upload_to_export_copy_error_is_upstream_s3_error() -> None:
    settings = Settings()
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=settings, s3_client=fake_s3)

    fake_s3.head_responses = [
        {"LastModified": "2024-01-01T00:00:00Z"},
    ]
    fake_s3.copy_error = BotoCoreError()

    with pytest.raises(FileTransferError) as exc_info:
        service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket,
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            job_id="job-1",
            filename="source.csv",
        )

    assert exc_info.value.code == "upstream_s3_error"
    assert exc_info.value.status_code == 502
    assert str(exc_info.value) == "failed to copy upload object to export key"


def test_copy_upload_to_export_client_error_is_upstream_s3_error() -> None:
    settings = Settings()
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=settings, s3_client=fake_s3)

    fake_s3.head_responses = [
        {"LastModified": "2024-01-01T00:00:00Z"},
    ]
    fake_s3.copy_error = ClientError(
        error_response={"Error": {"Code": "AccessDenied"}},
        operation_name="CopyObject",
    )

    with pytest.raises(FileTransferError) as exc_info:
        service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket,
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            job_id="job-1",
            filename="source.csv",
        )

    assert exc_info.value.code == "upstream_s3_error"
    assert exc_info.value.status_code == 502
    assert str(exc_info.value) == "failed to copy upload object to export key"
