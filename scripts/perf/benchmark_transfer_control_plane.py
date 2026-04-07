"""Benchmark current transfer initiate and sign-parts API throughput."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from urllib.parse import urlencode

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_app
from nova_file_api.auth import Authenticator
from nova_file_api.cache import LocalTTLCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.exports import (
    ExportService,
    MemoryExportPublisher,
    MemoryExportRepository,
)
from nova_file_api.models import Principal
from nova_file_api.runtime import ApiRuntime, build_idempotency_store
from nova_file_api.transfer import TransferService
from nova_file_api.transfer_config import transfer_config_from_settings
from nova_runtime_support.metrics import MetricsCollector
from scripts.perf.file_transfer_observability_baseline import (
    CURRENT_MAX_UPLOAD_BYTES,
    summarize_latency,
)

AUTH_HEADERS = {"Authorization": "Bearer token-123"}


class _StubAuthenticator:
    """Return a fixed principal for the perf harness."""

    async def authenticate(
        self,
        *,
        token: str | None,
    ) -> Principal:
        if token is None or not token.strip():
            raise ValueError("missing bearer token")
        return Principal(
            subject="bench-user",
            scope_id="scope-1",
            tenant_id=None,
            scopes=(),
            permissions=("metrics:read",),
        )

    async def healthcheck(self) -> bool:
        return True


class _PerfS3Client:
    """Minimal async S3 surface for current transfer API benchmarks."""

    async def generate_presigned_url(
        self,
        *,
        ClientMethod: str,
        Params: dict[str, Any],
        ExpiresIn: int,
    ) -> str:
        del ExpiresIn
        query = urlencode(
            {
                "upload_id": str(Params.get("UploadId", "missing")),
                "part": str(Params.get("PartNumber", "missing")),
            }
        )
        return (
            "https://example.local/"
            f"{ClientMethod}/"
            f"{Params.get('Key', 'missing')}"
            f"?{query}"
        )

    async def create_multipart_upload(self, **kwargs: Any) -> dict[str, str]:
        del kwargs
        return {"UploadId": "bench-upload-id"}


def _build_cache_stack() -> TwoTierCache:
    return TwoTierCache(
        local=LocalTTLCache(
            ttl_seconds=60,
            max_entries=128,
        )
    )


def _build_test_app(
    *,
    settings: Settings,
    metrics: MetricsCollector,
    transfer_service: TransferService,
    export_repository: MemoryExportRepository,
    export_service: ExportService,
) -> Any:
    cache = _build_cache_stack()
    idempotency_store = build_idempotency_store(
        settings=settings,
        dynamodb_resource=None,
    )
    runtime = ApiRuntime(
        settings=settings,
        metrics=metrics,
        cache=cache,
        authenticator=cast(Authenticator, cast(Any, _StubAuthenticator())),
        transfer_service=transfer_service,
        export_repository=export_repository,
        export_service=export_service,
        activity_store=MemoryActivityStore(),
        idempotency_store=idempotency_store,
    )
    return create_app(runtime=runtime)


async def _request_samples(
    *,
    client: httpx.AsyncClient,
    path: str,
    payload_factory: Callable[[], dict[str, object]],
    iterations: int,
) -> list[float]:
    samples_ms: list[float] = []
    for _ in range(iterations):
        payload = payload_factory()
        started = perf_counter()
        response = await client.post(path, headers=AUTH_HEADERS, json=payload)
        elapsed_ms = (perf_counter() - started) * 1000.0
        response.raise_for_status()
        samples_ms.append(elapsed_ms)
    return samples_ms


async def _main_async(args: argparse.Namespace) -> None:
    settings = Settings.model_validate(
        {
            "IDEMPOTENCY_ENABLED": False,
            "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
            "FILE_TRANSFER_BUCKET": "benchmark-bucket",
            "FILE_TRANSFER_MAX_UPLOAD_BYTES": CURRENT_MAX_UPLOAD_BYTES,
        }
    )
    metrics = MetricsCollector(namespace="PerfHarness")
    transfer_service = TransferService(
        config=transfer_config_from_settings(settings),
        s3_client=_PerfS3Client(),
    )
    export_repository = MemoryExportRepository()
    export_service = ExportService(
        repository=export_repository,
        publisher=MemoryExportPublisher(),
        metrics=metrics,
    )
    app = _build_test_app(
        settings=settings,
        metrics=metrics,
        transfer_service=transfer_service,
        export_repository=export_repository,
        export_service=export_service,
    )
    logging.getLogger().setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.ERROR)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        for _ in range(args.warmup):
            response = await client.post(
                "/v1/transfers/uploads/initiate",
                headers=AUTH_HEADERS,
                json={
                    "filename": "bench.csv",
                    "size_bytes": args.file_size_bytes,
                    "content_type": "text/csv",
                },
            )
            response.raise_for_status()

        initiate_samples = await _request_samples(
            client=client,
            path="/v1/transfers/uploads/initiate",
            payload_factory=lambda: {
                "filename": "bench.csv",
                "size_bytes": args.file_size_bytes,
                "content_type": "text/csv",
            },
            iterations=args.iterations,
        )
        initiate_response = await client.post(
            "/v1/transfers/uploads/initiate",
            headers=AUTH_HEADERS,
            json={
                "filename": "bench.csv",
                "size_bytes": args.file_size_bytes,
                "content_type": "text/csv",
            },
        )
        initiate_response.raise_for_status()
        initiate_payload = initiate_response.json()
        part_numbers = list(range(1, args.sign_part_count + 1))
        sign_samples = await _request_samples(
            client=client,
            path="/v1/transfers/uploads/sign-parts",
            payload_factory=lambda: {
                "key": initiate_payload["key"],
                "upload_id": initiate_payload["upload_id"],
                "part_numbers": part_numbers,
            },
            iterations=args.iterations,
        )

    print(
        json.dumps(
            {
                "mode": "transfer_control_plane_benchmark",
                "file_size_bytes": args.file_size_bytes,
                "iterations": args.iterations,
                "warmup": args.warmup,
                "initiate_ms": summarize_latency(
                    samples_ms=initiate_samples,
                    iterations=args.iterations,
                ),
                "sign_parts_ms": summarize_latency(
                    samples_ms=sign_samples,
                    iterations=args.iterations,
                ),
                "sign_part_count": args.sign_part_count,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__ or "transfer control plane benchmark"
    )
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=25)
    parser.add_argument(
        "--file-size-bytes",
        type=int,
        default=128 * 1024 * 1024,
    )
    parser.add_argument("--sign-part-count", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    """Run the benchmark entrypoint."""
    asyncio.run(_main_async(_parse_args()))


if __name__ == "__main__":
    main()
