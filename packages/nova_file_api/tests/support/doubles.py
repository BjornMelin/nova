"""Test doubles for nova_file_api auth and transfer interfaces."""

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
    """Authenticator test double that returns a fixed principal."""

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
        """Return True to indicate the stub is always healthy."""
        return True


class StubTransferService:
    """
    Transfer service test double that raises AssertionError on any call.

    Tests must stub or override methods when transfer behavior is needed.
    """

    async def initiate_upload(
        self,
        request: InitiateUploadRequest,
        principal: Principal,
    ) -> InitiateUploadResponse:
        del request, principal
        raise AssertionError("initiate_upload should be stubbed per test")

    async def sign_parts(
        self,
        request: SignPartsRequest,
        principal: Principal,
    ) -> SignPartsResponse:
        del request, principal
        raise AssertionError("sign_parts should be stubbed per test")

    async def complete_upload(
        self,
        request: CompleteUploadRequest,
        principal: Principal,
    ) -> CompleteUploadResponse:
        del request, principal
        raise AssertionError("complete_upload should be stubbed per test")

    async def abort_upload(
        self,
        request: AbortUploadRequest,
        principal: Principal,
    ) -> AbortUploadResponse:
        del request, principal
        raise AssertionError("abort_upload should be stubbed per test")

    async def presign_download(
        self,
        request: PresignDownloadRequest,
        principal: Principal,
    ) -> PresignDownloadResponse:
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
        del source_bucket, source_key, scope_id, job_id, filename
        raise AssertionError("copy_upload_to_export should be stubbed per test")
