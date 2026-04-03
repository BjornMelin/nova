"""Test doubles for nova_file_api auth and transfer interfaces."""

from __future__ import annotations

from nova_file_api.errors import unauthorized
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
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
)
from nova_file_api.transfer import ExportCopyResult
from nova_file_api.transfer_policy import TransferPolicy


class StubAuthenticator:
    """Authenticator test double that returns a fixed principal."""

    async def authenticate(
        self,
        *,
        token: str | None,
    ) -> Principal:
        if token is None or not token.strip():
            raise unauthorized("missing bearer token")
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

    async def resolve_policy(self, *, scope_id: str | None) -> TransferPolicy:
        """Return a stable default policy for capability route tests."""
        del scope_id
        return TransferPolicy(
            policy_id="default",
            policy_version="2026-04-03",
            max_upload_bytes=500 * 1024 * 1024 * 1024,
            multipart_threshold_bytes=100 * 1024 * 1024,
            target_upload_part_count=2000,
            minimum_part_size_bytes=64 * 1024 * 1024,
            maximum_part_size_bytes=512 * 1024 * 1024,
            upload_part_size_bytes=128 * 1024 * 1024,
            max_concurrency_hint=4,
            sign_batch_size_hint=32,
            accelerate_enabled=False,
            checksum_algorithm=None,
            resumable_ttl_seconds=7 * 24 * 60 * 60,
            active_multipart_upload_limit=200,
            daily_ingress_budget_bytes=1024 * 1024 * 1024 * 1024,
            sign_requests_per_upload_limit=512,
        )


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

    async def introspect_upload(
        self,
        request: UploadIntrospectionRequest,
        principal: Principal,
    ) -> UploadIntrospectionResponse:
        del request, principal
        raise AssertionError("introspect_upload should be stubbed per test")

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
        export_id: str,
        filename: str,
    ) -> ExportCopyResult:
        del source_bucket, source_key, scope_id, export_id, filename
        raise AssertionError("copy_upload_to_export should be stubbed per test")

    async def healthcheck(self) -> bool:
        """Return True to indicate the stub is always healthy."""
        return True
