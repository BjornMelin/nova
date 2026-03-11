from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import BotoCoreError, ClientError
from nova_file_api.config import Settings
from nova_file_api.errors import FileTransferError
from nova_file_api.models import (
    CompletedPart,
    CompleteUploadRequest,
    PresignDownloadRequest,
    Principal,
    UploadIntrospectionRequest,
)
from nova_file_api.transfer import TransferService


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
        self.multipart_upload_id = "upload-id"

    async def generate_presigned_url(
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
        if self.copy_error is not None:
            raise self.copy_error
        return {
            "CopyPartResult": {"ETag": f"etag-{kwargs['PartNumber']}"},
        }

    async def list_parts(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"list_parts": kwargs})
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


@pytest.fixture
def _service() -> tuple[TransferService, _FakeS3Client]:
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=Settings(), s3_client=fake_s3)
    return service, fake_s3


def _principal() -> Principal:
    return Principal(subject="user-1", scope_id="scope-1")


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
        == 'attachment; filename="reportfinal.csv"'
    )


@pytest.mark.asyncio
async def test_copy_upload_to_export_toctou_missing_source_is_invalid() -> None:
    settings = Settings()
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=settings, s3_client=fake_s3)

    fake_s3.head_responses = [
        {"LastModified": "2024-01-01T00:00:00Z", "ContentLength": 42},
    ]
    fake_s3.copy_error = ClientError(
        error_response={"Error": {"Code": "NoSuchKey"}},
        operation_name="CopyObject",
    )

    with pytest.raises(FileTransferError) as exc_info:
        await service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket,
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            job_id="job-1",
            filename="source.csv",
        )

    assert exc_info.value.code == "invalid_request"
    assert exc_info.value.status_code == 422
    assert str(exc_info.value) == "source upload object not found"


@pytest.mark.asyncio
async def test_copy_upload_to_export_copy_error_is_upstream_s3_error() -> None:
    settings = Settings()
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=settings, s3_client=fake_s3)

    fake_s3.head_responses = [
        {"LastModified": "2024-01-01T00:00:00Z", "ContentLength": 42},
    ]
    fake_s3.copy_error = BotoCoreError()

    with pytest.raises(FileTransferError) as exc_info:
        await service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket,
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            job_id="job-1",
            filename="source.csv",
        )

    assert exc_info.value.code == "upstream_s3_error"
    assert exc_info.value.status_code == 502
    assert str(exc_info.value) == "failed to copy upload object to export key"


@pytest.mark.asyncio
async def test_copy_upload_to_export_client_error_maps_to_upstream() -> None:
    settings = Settings()
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=settings, s3_client=fake_s3)

    fake_s3.head_responses = [
        {"LastModified": "2024-01-01T00:00:00Z", "ContentLength": 42},
    ]
    fake_s3.copy_error = ClientError(
        error_response={"Error": {"Code": "AccessDenied"}},
        operation_name="CopyObject",
    )

    with pytest.raises(FileTransferError) as exc_info:
        await service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket,
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            job_id="job-1",
            filename="source.csv",
        )

    assert exc_info.value.code == "upstream_s3_error"
    assert exc_info.value.status_code == 502
    assert str(exc_info.value) == "failed to copy upload object to export key"


@pytest.mark.asyncio
async def test_introspect_upload_lists_parts_across_pages() -> None:
    settings = Settings()
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=settings, s3_client=fake_s3)
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

    assert response.part_size_bytes == settings.file_transfer_part_size_bytes
    assert [part.model_dump() for part in response.parts] == [
        {"part_number": 1, "etag": '"etag-1"'},
        {"part_number": 2, "etag": '"etag-2"'},
    ]


@pytest.mark.asyncio
async def test_complete_upload_verifies_listed_parts_and_object_size() -> None:
    settings = Settings()
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=settings, s3_client=fake_s3)
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


@pytest.mark.asyncio
async def test_complete_upload_succeeds_when_post_complete_check_fails() -> (
    None
):
    settings = Settings()
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=settings, s3_client=fake_s3)
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


@pytest.mark.asyncio
async def test_complete_upload_rejects_missing_part() -> None:
    settings = Settings()
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=settings, s3_client=fake_s3)
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


@pytest.mark.asyncio
async def test_copy_upload_to_export_uses_multipart_copy_above_5_gb() -> None:
    settings = Settings.model_validate(
        {"FILE_TRANSFER_PART_SIZE_BYTES": 128 * 1024 * 1024}
    )
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=settings, s3_client=fake_s3)
    fake_s3.head_responses = [
        {
            "ContentLength": 5_000_000_001,
            "ContentType": "text/csv",
            "Metadata": {"source": "unit-test"},
        }
    ]

    result = await service.copy_upload_to_export(
        source_bucket=settings.file_transfer_bucket,
        source_key="uploads/scope-1/source.csv",
        scope_id="scope-1",
        job_id="job-1",
        filename="source.csv",
    )

    assert result.export_key.endswith("/source.csv")
    assert fake_s3.copy_calls == []
    assert fake_s3.multipart_upload_calls == [
        {
            "Bucket": settings.file_transfer_bucket,
            "Key": result.export_key,
            "ContentType": "text/csv",
            "Metadata": {"source": "unit-test"},
        }
    ]
    assert len(fake_s3.upload_part_copy_calls) > 1
    assert fake_s3.complete_calls[-1]["UploadId"] == fake_s3.multipart_upload_id


@pytest.mark.asyncio
async def test_copy_upload_to_export_aborts_failed_multipart_copy() -> None:
    settings = Settings.model_validate(
        {"FILE_TRANSFER_PART_SIZE_BYTES": 128 * 1024 * 1024}
    )
    fake_s3 = _FakeS3Client()
    fake_s3.copy_error = ClientError(
        error_response={"Error": {"Code": "AccessDenied"}},
        operation_name="UploadPartCopy",
    )
    service = TransferService(settings=settings, s3_client=fake_s3)
    fake_s3.head_responses = [{"ContentLength": 5_000_000_001}]

    with pytest.raises(FileTransferError) as exc_info:
        await service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket,
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            job_id="job-1",
            filename="source.csv",
        )

    assert exc_info.value.code == "upstream_s3_error"
    assert len(fake_s3.abort_calls) == 1


@pytest.mark.asyncio
async def test_copy_upload_to_export_large_copy_missing_source_is_invalid() -> (
    None
):
    settings = Settings.model_validate(
        {"FILE_TRANSFER_PART_SIZE_BYTES": 128 * 1024 * 1024}
    )
    fake_s3 = _FakeS3Client()
    fake_s3.copy_error = ClientError(
        error_response={"Error": {"Code": "NoSuchKey"}},
        operation_name="UploadPartCopy",
    )
    service = TransferService(settings=settings, s3_client=fake_s3)
    fake_s3.head_responses = [{"ContentLength": 5_000_000_001}]

    with pytest.raises(FileTransferError) as exc_info:
        await service.copy_upload_to_export(
            source_bucket=settings.file_transfer_bucket,
            source_key="uploads/scope-1/source.csv",
            scope_id="scope-1",
            job_id="job-1",
            filename="source.csv",
        )

    assert exc_info.value.code == "invalid_request"
    assert exc_info.value.status_code == 422
    assert str(exc_info.value) == "source upload object not found"
    assert len(fake_s3.abort_calls) == 1
