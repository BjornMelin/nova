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
        Act as a test-double placeholder for signing upload parts; raises unless replaced by a test-specific stub.
        
        Parameters:
            request (SignPartsRequest): Request describing which parts to sign.
            principal (Principal): Authenticated principal performing the operation.
        
        Returns:
            SignPartsResponse: Signed parts response.
        
        Raises:
            AssertionError: Raised when the method is called without being stubbed in a test.
        """
        del request, principal
        raise AssertionError("sign_parts should be stubbed per test")

    async def complete_upload(
        self,
        request: CompleteUploadRequest,
        principal: Principal,
    ) -> CompleteUploadResponse:
        """
        Test double for tests that raises if complete_upload is called without being explicitly stubbed.
        
        Parameters:
            request (CompleteUploadRequest): Ignored; present to match the production interface.
            principal (Principal): Ignored; present to match the production interface.
        
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
        Test double that intentionally fails when called unless a test provides a stub.
        
        Parameters:
            request (AbortUploadRequest): The abort upload request (ignored by this stub).
            principal (Principal): The caller's principal (ignored by this stub).
        
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
        Generate a presigned URL and associated metadata for downloading the requested object.
        
        Parameters:
            request (PresignDownloadRequest): Details of the object to presign (e.g., bucket/key, expiration).
            principal (Principal): The authenticated principal requesting the download; used to determine access and scope.
        
        Returns:
            PresignDownloadResponse: The presigned download URL and any required headers or fields for performing the download.
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
        Copy an uploaded object to an export location for a specific export job.
        
        Returns:
            ExportCopyResult: Result metadata about the copy operation.
        
        Raises:
            AssertionError: If this test double method has not been explicitly stubbed for the test.
        """
        del source_bucket, source_key, scope_id, job_id, filename
        raise AssertionError("copy_upload_to_export should be stubbed per test")
