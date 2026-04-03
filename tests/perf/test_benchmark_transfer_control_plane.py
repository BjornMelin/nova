"""Tests for the transfer control-plane benchmark harness."""

from __future__ import annotations

import pytest

from scripts.perf.benchmark_transfer_control_plane import _PerfS3Client


@pytest.mark.anyio
async def test_perf_s3_client_presigned_urls_vary_by_part() -> None:
    client = _PerfS3Client()

    first = await client.generate_presigned_url(
        ClientMethod="upload_part",
        Params={
            "Bucket": "benchmark-bucket",
            "Key": "uploads/scope-1/bench/source.csv",
            "UploadId": "upload-1",
            "PartNumber": 1,
        },
        ExpiresIn=900,
    )
    second = await client.generate_presigned_url(
        ClientMethod="upload_part",
        Params={
            "Bucket": "benchmark-bucket",
            "Key": "uploads/scope-1/bench/source.csv",
            "UploadId": "upload-1",
            "PartNumber": 2,
        },
        ExpiresIn=900,
    )

    assert first != second
    assert first.endswith("upload_id=upload-1&part=1")
    assert second.endswith("upload_id=upload-1&part=2")
