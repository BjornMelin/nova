from __future__ import annotations

from nova_file_api.models import (
    AbortUploadRequest,
    AbortUploadResponse,
    CompleteUploadRequest,
    CompleteUploadResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    PresignDownloadRequest,
    PresignDownloadResponse,
    Principal,
    SignPartsRequest,
    SignPartsResponse,
)
from nova_file_api.transfer import ExportCopyResult
from starlette.requests import Request


class StubAuthenticator:
    async def authenticate(
        self,
        *,
        request: Request,
        session_id: str | None,
    ) -> Principal:
        del request, session_id
        return Principal(
            subject="user-1",
            scope_id="scope-1",
            tenant_id=None,
            scopes=(),
            permissions=("metrics:read",),
        )

    async def healthcheck(self) -> bool:
        """Return healthy status for tests using this stub authenticator.

        Returns:
            ``True`` to indicate the test double is always healthy.
        """
        return True


class StubTransferService:
    """Async transfer test double that fails on unexpected calls."""

    async def initiate_upload(
        self,
        request: InitiateUploadRequest,
        principal: Principal,
    ) -> InitiateUploadResponse:
        """
        Test stub for initiating an upload; meant to be replaced by a test-specific stub.
        
        Parameters:
            request (InitiateUploadRequest): Upload initiation request details.
            principal (Principal): Authenticated principal performing the action.
        
        Returns:
            InitiateUploadResponse: Details required to begin the upload (e.g., upload ID, presigned URLs).
        
        Raises:
            AssertionError: Always raised in this test double to indicate the method must be stubbed per test.
        """
        del request, principal
        raise AssertionError("initiate_upload should be stubbed per test")

    async def sign_parts(
        self,
        request: SignPartsRequest,
        principal: Principal,
    ) -> SignPartsResponse:
        """
        Act as a test-double for signing upload parts; fails unless replaced by a test-specific stub.
        
        Returns:
            SignPartsResponse: The signed parts response when provided by a test stub.
        
        Raises:
            AssertionError: If called without being stubbed in a test.
        """
        del request, principal
        raise AssertionError("sign_parts should be stubbed per test")

    async def complete_upload(
        self,
        request: CompleteUploadRequest,
        principal: Principal,
    ) -> CompleteUploadResponse:
        """
        Test double that always raises an AssertionError to force explicit stubbing in tests.
        
        Raises:
            AssertionError: Always raised with message "complete_upload should be stubbed per test".
        """
        del request, principal
        raise AssertionError("complete_upload should be stubbed per test")

    async def abort_upload(
        self,
        request: AbortUploadRequest,
        principal: Principal,
    ) -> AbortUploadResponse:
        """
        Test double for aborting an upload that always fails unless a test provides a stub.
        
        Raises:
            AssertionError: Always raised with the message "abort_upload should be stubbed per test".
        """
        del request, principal
        raise AssertionError("abort_upload should be stubbed per test")

    async def presign_download(
        self,
        request: PresignDownloadRequest,
        principal: Principal,
    ) -> PresignDownloadResponse:
        """
        Create a presigned download URL and associated headers or form fields for the requested object.
        
        Parameters:
            principal (Principal): Authenticated principal used to determine access and scope for the request.
        
        Returns:
            PresignDownloadResponse: The presigned URL and any required headers or fields to perform the download.
        """
        del request, principal
        raise AssertionError("presign_download should be stubbed per test")

    async def copy_upload_to_export(
        self,
        *,
        source_bucket: str,
        source_key: str,
        scope_id: str,
        job_id: str,
        filename: str,
    ) -> ExportCopyResult:
        """
        Copy an uploaded object to the export location for a given export job.
        
        Returns:
            ExportCopyResult: Metadata about the copy operation (for example destination location and object attributes).
        
        Raises:
            AssertionError: If this test double method has not been explicitly stubbed for the test.
        """
        del source_bucket, source_key, scope_id, job_id, filename
        raise AssertionError("copy_upload_to_export should be stubbed per test")