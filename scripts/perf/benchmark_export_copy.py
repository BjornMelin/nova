"""Benchmark the inline export-copy control-plane path."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tracemalloc
from pathlib import Path
from time import perf_counter
from typing import Any

from botocore.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from nova_file_api.config import Settings
from nova_file_api.transfer import TransferService
from nova_file_api.transfer_config import transfer_config_from_settings
from scripts.perf.file_transfer_observability_baseline import (
    bytes_text,
    gibibytes,
)


class _PerfS3Client:
    """Fake S3 client used to benchmark control-plane orchestration only."""

    def __init__(self, *, source_size_bytes: int) -> None:
        self._source_size_bytes = source_size_bytes
        self.copy_calls: list[dict[str, Any]] = []
        self.multipart_upload_calls: list[dict[str, Any]] = []
        self.upload_part_copy_calls: list[dict[str, Any]] = []
        self.complete_calls: list[dict[str, Any]] = []
        self.abort_calls: list[dict[str, Any]] = []
        self.max_in_flight = 0
        self._in_flight = 0

    async def head_object(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return {
            "ContentLength": self._source_size_bytes,
            "ContentType": "text/csv",
        }

    async def copy_object(self, **kwargs: Any) -> dict[str, Any]:
        self.copy_calls.append(kwargs)
        return {}

    async def create_multipart_upload(self, **kwargs: Any) -> dict[str, str]:
        self.multipart_upload_calls.append(kwargs)
        return {"UploadId": "perf-upload-id"}

    async def upload_part_copy(self, **kwargs: Any) -> dict[str, Any]:
        self.upload_part_copy_calls.append(kwargs)
        self._in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self._in_flight)
        await asyncio.sleep(0)
        self._in_flight -= 1
        return {
            "CopyPartResult": {
                "ETag": f"etag-{kwargs['PartNumber']}",
            }
        }

    async def complete_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        self.complete_calls.append(kwargs)
        return {"ETag": "export-etag"}

    async def abort_multipart_upload(self, **kwargs: Any) -> dict[str, Any]:
        self.abort_calls.append(kwargs)
        return {}


def _settings(
    *,
    part_size_bytes: int,
    max_concurrency: int,
) -> Settings:
    return Settings.model_validate(
        {
            "IDEMPOTENCY_ENABLED": False,
            "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
            "FILE_TRANSFER_BUCKET": "benchmark-bucket",
            "FILE_TRANSFER_PART_SIZE_BYTES": part_size_bytes,
            "FILE_TRANSFER_MAX_CONCURRENCY": max_concurrency,
            "FILE_TRANSFER_USE_ACCELERATE_ENDPOINT": False,
        }
    )


async def _benchmark_case(
    *,
    source_size_bytes: int,
    iterations: int,
    part_size_bytes: int,
    max_concurrency: int,
) -> dict[str, object]:
    latencies_ms: list[float] = []
    peak_memory_bytes = 0
    part_count = 0
    strategy = "copy_object"
    max_in_flight = 0
    for _ in range(iterations):
        fake_s3 = _PerfS3Client(source_size_bytes=source_size_bytes)
        service = TransferService(
            config=transfer_config_from_settings(
                _settings(
                    part_size_bytes=part_size_bytes,
                    max_concurrency=max_concurrency,
                )
            ),
            s3_client=fake_s3,
        )
        tracemalloc.start()
        started = perf_counter()
        await service.copy_upload_to_export(
            source_bucket="benchmark-bucket",
            source_key="uploads/scope-1/bench/source.csv",
            scope_id="scope-1",
            export_id="export-1",
            filename="source.csv",
        )
        elapsed_ms = (perf_counter() - started) * 1000.0
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        latencies_ms.append(elapsed_ms)
        peak_memory_bytes = max(peak_memory_bytes, peak)
        part_count = len(fake_s3.upload_part_copy_calls)
        strategy = (
            "multipart_copy"
            if fake_s3.upload_part_copy_calls
            else "copy_object"
        )
        max_in_flight = max(max_in_flight, fake_s3.max_in_flight)

    avg_ms = sum(latencies_ms) / len(latencies_ms)
    return {
        "source_size_bytes": source_size_bytes,
        "source_size_human": bytes_text(source_size_bytes),
        "iterations": iterations,
        "strategy": strategy,
        "part_size_bytes": part_size_bytes,
        "part_size_human": bytes_text(part_size_bytes),
        "max_concurrency": max_concurrency,
        "multipart_part_count": part_count,
        "avg_elapsed_ms": round(avg_ms, 3),
        "max_peak_memory_bytes": peak_memory_bytes,
        "max_peak_memory_human": bytes_text(peak_memory_bytes),
        "max_upload_part_copy_in_flight": max_in_flight,
    }


async def _main_async(args: argparse.Namespace) -> None:
    sizes = [gibibytes(float(item)) for item in args.sizes_gib.split(",")]
    results = [
        await _benchmark_case(
            source_size_bytes=source_size_bytes,
            iterations=args.iterations,
            part_size_bytes=args.part_size_bytes,
            max_concurrency=args.max_concurrency,
        )
        for source_size_bytes in sizes
    ]
    print(
        json.dumps(
            {
                "mode": "inline_export_copy_benchmark",
                "runtime": {
                    "part_size_bytes": args.part_size_bytes,
                    "max_concurrency": args.max_concurrency,
                    "botocore_s3_config": Config().s3 or {},
                },
                "results": results,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )


def main() -> None:
    """Run the inline export-copy benchmark."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sizes-gib",
        default="6,50,500",
        help="Comma-separated source object sizes in GiB.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=2,
        help="Iterations per size.",
    )
    parser.add_argument(
        "--part-size-bytes",
        type=int,
        default=128 * 1024 * 1024,
        help="Current inline export copy part size in bytes.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Current inline export copy concurrency.",
    )
    args = parser.parse_args()
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
