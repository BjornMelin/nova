"""Shared test utilities for building FastAPI apps with dependency overrides."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

import httpx
from fastapi import FastAPI
from nova_file_api.activity import ActivityStore
from nova_file_api.app import create_app
from nova_file_api.cache import LocalTTLCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.dependencies import (
    build_idempotency_store,
    get_activity_store,
    get_authenticator,
    get_export_repository,
    get_export_service,
    get_idempotency_store,
    get_metrics,
    get_transfer_service,
    get_two_tier_cache,
)
from nova_file_api.exports import ExportRepository
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.metrics import MetricsCollector

from .dynamodb import MemoryDynamoResource

_T = TypeVar("_T")
_TEST_IDEMPOTENCY_TABLE = "test-idempotency"


@dataclass(slots=True)
class RuntimeDeps:
    """Container for test doubles installed via FastAPI dependency overrides."""

    settings: Settings
    metrics: MetricsCollector
    cache: TwoTierCache
    authenticator: object
    transfer_service: object
    export_service: object
    activity_store: ActivityStore
    idempotency_store: IdempotencyStore
    export_repository: ExportRepository | None = None
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
    resolved_settings.idempotency_dynamodb_table = _TEST_IDEMPOTENCY_TABLE

    resolved_idempotency_store = idempotency_store or build_idempotency_store(
        settings=resolved_settings,
        dynamodb_resource=resolved_dynamodb,
    )

    return RuntimeDeps(
        settings=resolved_settings,
        metrics=resolved_metrics,
        cache=resolved_cache,
        authenticator=authenticator,
        transfer_service=transfer_service,
        export_service=export_service,
        activity_store=activity_store,
        idempotency_store=resolved_idempotency_store,
        export_repository=export_repository,
        dynamodb_resource=resolved_dynamodb,
    )


def build_test_app(deps: RuntimeDeps) -> FastAPI:
    """Create a FastAPI app with dependency overrides from the given deps."""
    from nova_file_api.dependencies import get_settings

    def _override(value: _T) -> Callable[[], Awaitable[_T]]:
        async def _provider() -> _T:
            return value

        return _provider

    app = create_app(settings=deps.settings)
    app.state._skip_runtime_state_initialization = True
    app.state._two_tier_cache_provider = lambda: deps.cache
    app.state._idempotency_store_provider = lambda: deps.idempotency_store
    app.state.cache = deps.cache
    app.state.authenticator = deps.authenticator
    app.state.settings = deps.settings
    app.dependency_overrides[get_settings] = _override(deps.settings)
    app.dependency_overrides[get_metrics] = _override(deps.metrics)
    app.dependency_overrides[get_two_tier_cache] = _override(deps.cache)
    app.dependency_overrides[get_authenticator] = _override(deps.authenticator)
    app.dependency_overrides[get_transfer_service] = _override(
        deps.transfer_service
    )
    if deps.export_repository is not None:
        app.dependency_overrides[get_export_repository] = _override(
            deps.export_repository
        )
    app.dependency_overrides[get_export_service] = _override(
        deps.export_service
    )
    app.dependency_overrides[get_activity_store] = _override(
        deps.activity_store
    )
    app.dependency_overrides[get_idempotency_store] = _override(
        deps.idempotency_store
    )
    return app


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
