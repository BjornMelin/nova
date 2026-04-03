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
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_app
from nova_file_api.cache import LocalTTLCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.dependencies import (
    build_idempotency_store,
    get_activity_store,
    get_authenticator,
    get_export_service,
    get_idempotency_store,
    get_metrics,
    get_settings,
    get_transfer_service,
    get_two_tier_cache,
)
from nova_file_api.exports import (
    ExportService,
    MemoryExportPublisher,
    MemoryExportRepository,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import Principal
from nova_file_api.transfer import TransferService
from nova_file_api.transfer_config import transfer_config_from_settings
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
        return (
            "https://example.local/"
            f"{ClientMethod}/"
            f"{Params.get('Key', 'missing')}"
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
    export_service: ExportService,
) -> Any:
    app = create_app(settings=settings)
    cache = _build_cache_stack()
    idempotency_store = build_idempotency_store(
        settings=settings,
        dynamodb_resource=None,
    )

    def _override(value: object) -> Callable[[], object]:
        def _provider() -> object:
            return value

        return _provider

    app.state._skip_runtime_state_initialization = True
    app.state.cache = cache
    app.state.authenticator = _StubAuthenticator()
    app.state.settings = settings
    app.dependency_overrides[get_settings] = _override(settings)
    app.dependency_overrides[get_metrics] = _override(metrics)
    app.dependency_overrides[get_two_tier_cache] = _override(cache)
    app.dependency_overrides[get_authenticator] = _override(
        _StubAuthenticator()
    )
    app.dependency_overrides[get_transfer_service] = _override(transfer_service)
    app.dependency_overrides[get_export_service] = _override(export_service)
    app.dependency_overrides[get_activity_store] = _override(
        MemoryActivityStore()
    )
    app.dependency_overrides[get_idempotency_store] = _override(
        idempotency_store
    )
    return app


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
    export_service = ExportService(
        repository=MemoryExportRepository(),
        publisher=MemoryExportPublisher(),
        metrics=metrics,
    )
    app = _build_test_app(
        settings=settings,
        metrics=metrics,
        transfer_service=transfer_service,
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
                "sign_part_count": args.sign_part_count,
                "initiate": {
                    **summarize_latency(
                        samples_ms=initiate_samples,
                        iterations=args.iterations,
                    ),
                    "throughput_rps": round(
                        args.iterations / (sum(initiate_samples) / 1000.0),
                        3,
                    ),
                },
                "sign_parts": {
                    **summarize_latency(
                        samples_ms=sign_samples,
                        iterations=args.iterations,
                    ),
                    "throughput_rps": round(
                        args.iterations / (sum(sign_samples) / 1000.0),
                        3,
                    ),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


def main() -> None:
    """Run the current transfer control-plane API benchmark."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--iterations",
        type=int,
        default=25,
        help="Measured iterations per route.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=5,
        help="Warmup iterations before timing.",
    )
    parser.add_argument(
        "--file-size-bytes",
        type=int,
        default=500 * 1024 * 1024 * 1024,
        help="Upload size used for initiate requests.",
    )
    parser.add_argument(
        "--sign-part-count",
        type=int,
        default=8,
        help="Number of parts requested in each sign-parts call.",
    )
    args = parser.parse_args()
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
