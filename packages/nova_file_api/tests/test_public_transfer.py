from __future__ import annotations

from typing import Any, cast

import pytest

import nova_file_api.public as public


class _FakeTransferStorageClient:
    async def generate_presigned_url(self, **kwargs: object) -> str:
        del kwargs
        return "https://example.invalid/presigned"

    async def create_multipart_upload(
        self, **kwargs: object
    ) -> dict[str, object]:
        raise AssertionError(f"unexpected call: {kwargs}")

    async def complete_multipart_upload(
        self, **kwargs: object
    ) -> dict[str, object]:
        raise AssertionError(f"unexpected call: {kwargs}")

    async def abort_multipart_upload(
        self, **kwargs: object
    ) -> dict[str, object]:
        raise AssertionError(f"unexpected call: {kwargs}")

    async def head_object(self, **kwargs: object) -> dict[str, object]:
        raise AssertionError(f"unexpected call: {kwargs}")

    async def list_parts(self, **kwargs: object) -> dict[str, object]:
        raise AssertionError(f"unexpected call: {kwargs}")

    async def copy_object(self, **kwargs: object) -> dict[str, object]:
        raise AssertionError(f"unexpected call: {kwargs}")

    async def upload_part_copy(self, **kwargs: object) -> dict[str, object]:
        raise AssertionError(f"unexpected call: {kwargs}")


def test_transfer_config_is_keyword_only() -> None:
    constructor = cast(Any, public.TransferConfig)
    with pytest.raises(TypeError):
        constructor(
            True,
            "bucket-a",
            "uploads/",
            "exports/",
            "tmp/",
            900,
            900,
            10 * 1024 * 1024,
            10 * 1024 * 1024,
            4,
            False,
            500 * 1024 * 1024,
        )


@pytest.mark.anyio
async def test_build_transfer_service_ignores_ambient_settings_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXPORTS_ENABLED", "false")

    service = public.build_transfer_service(
        config=public.TransferConfig(
            enabled=True,
            bucket="bucket-a",
            upload_prefix="uploads/",
            export_prefix="exports/",
            tmp_prefix="tmp/",
            presign_upload_ttl_seconds=900,
            presign_download_ttl_seconds=900,
            multipart_threshold_bytes=10 * 1024 * 1024,
            part_size_bytes=10 * 1024 * 1024,
            max_concurrency=4,
            use_accelerate_endpoint=False,
            max_upload_bytes=500 * 1024 * 1024,
        ),
        s3_client=_FakeTransferStorageClient(),
    )

    response = await service.initiate_upload(
        public.InitiateUploadRequest(
            filename="report.csv",
            content_type="text/csv",
            size_bytes=1,
        ),
        public.Principal(subject="user-1", scope_id="scope-1"),
    )

    assert response.bucket == "bucket-a"
    assert response.url == "https://example.invalid/presigned"


def test_public_surface_keeps_error_envelope_but_not_error_body() -> None:
    assert hasattr(public, "ErrorEnvelope")
    assert not hasattr(public, "ErrorBody")
    assert hasattr(public, "AsyncTransferService")
    assert not hasattr(public, "TransferFacadeConfig")
    assert not hasattr(public, "TransferService")
