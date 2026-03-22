from __future__ import annotations

import nova_file_api.public as public
import pytest
from nova_file_api.transfer import TransferService


def test_build_transfer_service_ignores_ambient_settings_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOBS_RUNTIME_MODE", "worker")

    service = public.build_transfer_service(
        config=public.TransferFacadeConfig(
            file_transfer_enabled=True,
            file_transfer_bucket="bucket-a",
            file_transfer_upload_prefix="uploads/",
            file_transfer_export_prefix="exports/",
            file_transfer_tmp_prefix="tmp/",
            file_transfer_presign_upload_ttl_seconds=900,
            file_transfer_presign_download_ttl_seconds=900,
            file_transfer_multipart_threshold_bytes=10 * 1024 * 1024,
            file_transfer_part_size_bytes=10 * 1024 * 1024,
            file_transfer_max_concurrency=4,
            file_transfer_use_accelerate_endpoint=False,
            max_upload_bytes=500 * 1024 * 1024,
        ),
        s3_client=object(),
    )

    assert isinstance(service, TransferService)
    assert service.settings.jobs_runtime_mode == "api"
    assert service.settings.file_transfer_bucket == "bucket-a"


def test_public_surface_keeps_error_envelope_but_not_error_body() -> None:
    assert hasattr(public, "ErrorEnvelope")
    assert not hasattr(public, "ErrorBody")
