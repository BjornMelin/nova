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
        """
        Initialize the fake S3 client's internal state used by tests.
        
        Attributes:
            calls (list[dict[str, Any]]): Recorded parameters for generate_presigned_url calls.
            copy_calls (list[dict[str, Any]]): Recorded keyword arguments passed to copy_object calls.
            copy_error (Exception | None): If set, exception to raise when copy_object is invoked.
            head_responses (list[dict[str, Any] | Exception]): Queue of responses or exceptions returned/raised by head_object; items are popped in FIFO order.
        """
        self.calls: list[dict[str, Any]] = []
        self.copy_calls: list[dict[str, Any]] = []
        self.copy_error: Exception | None = None
        self.head_responses: list[dict[str, Any] | Exception] = []

    async def generate_presigned_url(
        self,
        *,
        ClientMethod: str,
        Params: dict[str, Any],
        ExpiresIn: int,
    ) -> str:
        """
        Record details of a presigned URL generation request and return a fixed presigned URL.
        
        Parameters:
            ClientMethod (str): S3 client operation name for which the presigned URL is requested (for example, "get_object").
            Params (dict[str, Any]): Parameters that would be passed to the S3 operation.
            ExpiresIn (int): Expiration time in seconds for the presigned URL.
        
        Returns:
            str: The fixed presigned URL "https://example.local/presigned".
        """
        self.calls.append(
            {
                "ClientMethod": ClientMethod,
                "Params": Params,
                "ExpiresIn": ExpiresIn,
            }
        )
        return "https://example.local/presigned"

    async def head_object(self, **kwargs: Any) -> dict[str, Any]:
        """
        Provide the next queued head_object response or raise a queued exception.
        
        If a prepared response was queued, this method pops and returns it. If the queued
        item is an Exception, that exception is raised. If no response is queued, an
        empty dict is returned.
        
        Returns:
            dict: The head_object response metadata; empty dict if no queued responses.
        
        Raises:
            Exception: The queued exception if the next queued item is an Exception.
        """
        del kwargs
        if self.head_responses:
            item = self.head_responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return {}

    async def copy_object(self, **kwargs: Any) -> dict[str, Any]:
        """
        Record a mocked S3 CopyObject call, optionally raise a preconfigured error, and return an empty response.
        
        Parameters:
            **kwargs: Arbitrary keyword arguments forwarded as the parameters of the simulated S3 CopyObject call.
        
        Returns:
            response (dict[str, Any]): An empty dictionary representing the mocked S3 response.
        
        Raises:
            Exception: The exception stored in `self.copy_error`, if set.
        """
        self.copy_calls.append(kwargs)
        if self.copy_error is not None:
            raise self.copy_error
        return {}

    async def create_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        """
        Initiate a multipart upload and return a mock upload identifier.
        
        Returns:
            dict: Mapping with key "UploadId" containing the mocked upload identifier.
        """
        del kwargs
        return {"UploadId": "upload-id"}

    async def complete_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        """
        Return a fixed completion response for a multipart upload.
        
        Returns:
            dict: A mapping with keys `ETag` (the object's entity tag) and `VersionId` (the object version identifier).
        """
        del kwargs
        return {"ETag": "etag", "VersionId": "version"}

    async def abort_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        """
        Mock abort of a multipart upload; returns an empty response suitable for tests.
        
        Returns:
            response (dict): An empty dictionary representing a successful abort operation.
        """
        del kwargs
        return {}


@pytest.fixture
def _service() -> tuple[TransferService, _FakeS3Client]:
    """
    Create a TransferService instance wired to a fake S3 client for use in tests.
    
    Returns:
        (service, fake_s3): Tuple where `service` is a TransferService configured with default Settings
        and `fake_s3` is the corresponding `_FakeS3Client` instance used to inspect and control S3 interactions.
    """
    fake_s3 = _FakeS3Client()
    service = TransferService(settings=Settings(), s3_client=fake_s3)
    return service, fake_s3


def _principal() -> Principal:
    """
    Create a test Principal representing a default user in scope "scope-1".
    
    Returns:
        Principal: A Principal with subject "user-1" and scope_id "scope-1".
    """
    return Principal(subject="user-1", scope_id="scope-1")


@pytest.mark.asyncio
async def test_presign_download_preserves_explicit_content_disposition(
    _service: tuple[TransferService, _FakeS3Client],
) -> None:
    """
    Verify presign_download preserves an explicit Content-Disposition and does not add ResponseContentType.
    
    Calls presign_download with a request that supplies an explicit `content_disposition` and asserts the S3 presign parameters contain `ResponseContentDisposition` exactly as given and omit `ResponseContentType`.
    """
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
    """
    Ensure copy_upload_to_export reports a missing source object as an invalid request.
    
    Sets up a head_object response followed by a CopyObject failure with S3 error code "NoSuchKey" and asserts that the service raises FileTransferError with:
    - code: "invalid_request"
    - status_code: 422
    - message: "source upload object not found"
    """
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
        {"LastModified": "2024-01-01T00:00:00Z"},
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
        {"LastModified": "2024-01-01T00:00:00Z"},
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
