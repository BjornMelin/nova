"""Shared test utilities for building FastAPI apps with public runtime seams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import httpx
from fastapi import FastAPI

from nova_file_api.activity import ActivityStore
from nova_file_api.app import create_app
from nova_file_api.auth import Authenticator
from nova_file_api.cache import LocalTTLCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.export_runtime import ExportRepository
from nova_file_api.exports import ExportService, MemoryExportRepository
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.runtime import ApiRuntime, build_idempotency_store
from nova_file_api.transfer import TransferService
from nova_runtime_support.metrics import MetricsCollector

from .dynamodb import MemoryDynamoResource

_TEST_IDEMPOTENCY_TABLE = "test-idempotency"


@dataclass(slots=True)
class RuntimeDeps:
    """Container for test doubles installed via the public runtime builder."""

    settings: Settings
    metrics: MetricsCollector
    cache: TwoTierCache
    authenticator: object
    transfer_service: object
    export_service: object
    activity_store: ActivityStore
    idempotency_store: IdempotencyStore
    export_repository: ExportRepository
    dynamodb_resource: MemoryDynamoResource | None = None


def build_cache_stack(
    *,
    ttl_seconds: int = 60,
    max_entries: int = 128,
) -> TwoTierCache:
    """Build a local cache stack used by API-style tests."""
    return TwoTierCache(
        local=LocalTTLCache(
            ttl_seconds=ttl_seconds,
            max_entries=max_entries,
        )
    )


def build_runtime_deps(
    *,
    authenticator: object,
    transfer_service: object,
    export_service: object,
    activity_store: ActivityStore,
    settings: Settings | None = None,
    metrics: MetricsCollector | None = None,
    cache: TwoTierCache | None = None,
    idempotency_store: IdempotencyStore | None = None,
    idempotency_enabled: bool = True,
    idempotency_ttl_seconds: int = 300,
    export_repository: ExportRepository | None = None,
    dynamodb_resource: MemoryDynamoResource | None = None,
) -> RuntimeDeps:
    """Build a runtime dependency graph for route tests."""
    resolved_settings = (
        Settings.model_validate(
            {"IDEMPOTENCY_DYNAMODB_TABLE": _TEST_IDEMPOTENCY_TABLE}
        )
        if settings is None
        else settings
    )
    resolved_metrics = (
        MetricsCollector(namespace="Tests") if metrics is None else metrics
    )
    resolved_cache = build_cache_stack() if cache is None else cache
    resolved_dynamodb = (
        MemoryDynamoResource()
        if dynamodb_resource is None
        else dynamodb_resource
    )

    resolved_settings.idempotency_enabled = idempotency_enabled
    resolved_settings.idempotency_ttl_seconds = idempotency_ttl_seconds
    if not (resolved_settings.idempotency_dynamodb_table or "").strip():
        resolved_settings.idempotency_dynamodb_table = _TEST_IDEMPOTENCY_TABLE

    resolved_idempotency_store = idempotency_store or build_idempotency_store(
        settings=resolved_settings,
        dynamodb_resource=resolved_dynamodb,
    )
    resolved_export_repository = export_repository or cast(
        ExportRepository | None,
        getattr(export_service, "repository", None),
    )
    if resolved_export_repository is None:
        resolved_export_repository = MemoryExportRepository()

    return RuntimeDeps(
        settings=resolved_settings,
        metrics=resolved_metrics,
        cache=resolved_cache,
        authenticator=authenticator,
        transfer_service=transfer_service,
        export_service=export_service,
        activity_store=activity_store,
        idempotency_store=resolved_idempotency_store,
        export_repository=resolved_export_repository,
        dynamodb_resource=resolved_dynamodb,
    )


def build_test_runtime(deps: RuntimeDeps) -> ApiRuntime:
    """Create a typed runtime container from resolved test doubles."""
    return ApiRuntime(
        settings=deps.settings,
        metrics=deps.metrics,
        cache=deps.cache,
        authenticator=cast(Authenticator, cast(Any, deps.authenticator)),
        transfer_service=cast(
            TransferService,
            cast(Any, deps.transfer_service),
        ),
        export_repository=deps.export_repository,
        export_service=cast(
            ExportService,
            cast(Any, deps.export_service),
        ),
        activity_store=deps.activity_store,
        idempotency_store=deps.idempotency_store,
    )


def build_test_app(deps: RuntimeDeps) -> FastAPI:
    """Create a FastAPI app from the given runtime doubles."""
    return create_app(runtime=build_test_runtime(deps))


async def request_app(
    app: FastAPI,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json: dict[str, object] | None = None,
    raise_app_exceptions: bool = True,
) -> httpx.Response:
    """Execute one request against a test app within its lifespan."""
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=app,
                raise_app_exceptions=raise_app_exceptions,
            ),
            base_url="http://testserver",
        ) as client,
    ):
        return await client.request(
            method,
            path,
            headers=headers,
            json=json,
        )
