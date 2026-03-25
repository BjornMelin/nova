"""Shared test utilities for building FastAPI apps with dependency overrides."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

import httpx
from fastapi import FastAPI
from nova_file_api.activity import ActivityStore
from nova_file_api.app import create_app
from nova_file_api.cache import LocalTTLCache, SharedRedisCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.dependencies import (
    build_idempotency_store,
    get_activity_store,
    get_authenticator,
    get_idempotency_store,
    get_job_repository,
    get_job_service,
    get_metrics,
    get_shared_cache,
    get_transfer_service,
    get_two_tier_cache,
)
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.jobs import JobRepository
from nova_file_api.metrics import MetricsCollector

from .redis import MemoryRedisClient

_T = TypeVar("_T")


@dataclass(slots=True)
class RuntimeDeps:
    """
    Container for test doubles installed via FastAPI dependency overrides.

    All fields are required except job_repository, which is optional.
    """

    settings: Settings
    metrics: MetricsCollector
    shared_cache: SharedRedisCache
    cache: TwoTierCache
    authenticator: object
    transfer_service: object
    job_service: object
    activity_store: ActivityStore
    idempotency_store: IdempotencyStore
    job_repository: JobRepository | None = None


def build_cache_stack(
    *,
    ttl_seconds: int = 60,
    max_entries: int = 128,
    shared_ttl_seconds: int = 60,
) -> tuple[SharedRedisCache, TwoTierCache]:
    """
    Build a two-tier cache stack used by API-style tests.

    Args:
        ttl_seconds: Local cache TTL in seconds.
        max_entries: Maximum entries in the local cache.
        shared_ttl_seconds: Shared cache TTL in seconds.

    Returns:
        Tuple of (shared_cache, two_tier_cache).
    """
    shared_cache = SharedRedisCache(url=None)
    cache = TwoTierCache(
        local=LocalTTLCache(
            ttl_seconds=ttl_seconds,
            max_entries=max_entries,
        ),
        shared=shared_cache,
        shared_ttl_seconds=shared_ttl_seconds,
    )
    return shared_cache, cache


def build_runtime_deps(
    *,
    authenticator: object,
    transfer_service: object,
    job_service: object,
    activity_store: ActivityStore,
    settings: Settings | None = None,
    metrics: MetricsCollector | None = None,
    shared_cache: SharedRedisCache | None = None,
    cache: TwoTierCache | None = None,
    idempotency_store: IdempotencyStore | None = None,
    use_in_memory_shared_cache: bool = False,
    idempotency_enabled: bool = True,
    idempotency_ttl_seconds: int = 300,
    job_repository: JobRepository | None = None,
) -> RuntimeDeps:
    """
    Build a runtime dependency graph for route tests.

    Args:
        authenticator: Auth implementation to inject.
        transfer_service: Transfer service implementation.
        job_service: Job service implementation.
        activity_store: Activity store implementation.
        settings: Optional settings; defaults to Settings().
        metrics: Optional metrics; defaults to MetricsCollector.
        shared_cache: Shared cache; built via build_cache_stack if None.
        cache: Two-tier cache; built via build_cache_stack if None.
        use_in_memory_shared_cache: If ``True``, build an in-memory cache stack
            for tests.
        idempotency_store: Idempotency store; built from cache if None.
        idempotency_enabled: Whether idempotency is enabled when building store.
        idempotency_ttl_seconds: TTL for idempotency store when building.
        job_repository: Optional job repository override.

    Returns:
        RuntimeDeps instance ready for build_test_app.
    """
    resolved_settings = (
        Settings.model_validate({}) if settings is None else settings
    )
    resolved_metrics = (
        MetricsCollector(namespace="Tests") if metrics is None else metrics
    )
    resolved_settings.idempotency_enabled = idempotency_enabled
    resolved_settings.idempotency_ttl_seconds = idempotency_ttl_seconds
    if (shared_cache is None) != (cache is None):
        raise ValueError(
            "shared_cache and cache must both be provided or both be None"
        )
    if shared_cache is None and cache is None:
        if use_in_memory_shared_cache:
            resolved_shared_cache, resolved_cache = build_cache_stack()
            resolved_shared_cache._client = MemoryRedisClient()
        elif idempotency_enabled:
            raise ValueError(
                "idempotency_enabled requires shared_cache/cache or "
                "use_in_memory_shared_cache in tests; cache_redis_url is not "
                f"auto-bound here ({resolved_settings.cache_redis_url!r})"
            )
        else:
            resolved_shared_cache = SharedRedisCache(url=None)
            resolved_cache = TwoTierCache(
                local=LocalTTLCache(
                    ttl_seconds=60,
                    max_entries=128,
                ),
                shared=resolved_shared_cache,
                shared_ttl_seconds=60,
            )
    else:
        assert shared_cache is not None
        assert cache is not None
        resolved_shared_cache = shared_cache
        resolved_cache = cache
        if use_in_memory_shared_cache:
            resolved_shared_cache._client = MemoryRedisClient()
    resolved_idempotency_store = idempotency_store or build_idempotency_store(
        settings=resolved_settings,
        shared_cache=resolved_shared_cache,
    )
    return RuntimeDeps(
        settings=resolved_settings,
        metrics=resolved_metrics,
        shared_cache=resolved_shared_cache,
        cache=resolved_cache,
        authenticator=authenticator,
        transfer_service=transfer_service,
        job_service=job_service,
        activity_store=activity_store,
        idempotency_store=resolved_idempotency_store,
        job_repository=job_repository,
    )


def build_test_app(deps: RuntimeDeps) -> FastAPI:
    """
    Create a FastAPI app with dependency overrides from the given deps.

    Args:
        deps: Runtime dependency container with test doubles.

    Returns:
        Configured FastAPI app instance.
    """
    from nova_file_api.dependencies import get_settings

    def _override(value: _T) -> Callable[[], Awaitable[_T]]:
        async def _provider() -> _T:
            return value

        return _provider

    app = create_app(settings=deps.settings)
    app.state._skip_runtime_state_initialization = True
    app.state._shared_cache_provider = lambda: deps.shared_cache
    app.state._two_tier_cache_provider = lambda: deps.cache
    app.state._idempotency_store_provider = lambda: deps.idempotency_store
    app.state.shared_cache = deps.shared_cache
    app.state.cache = deps.cache
    app.state.authenticator = deps.authenticator
    app.state.settings = deps.settings
    app.dependency_overrides[get_settings] = _override(deps.settings)
    app.dependency_overrides[get_metrics] = _override(deps.metrics)
    app.dependency_overrides[get_shared_cache] = _override(deps.shared_cache)
    app.dependency_overrides[get_two_tier_cache] = _override(deps.cache)
    app.dependency_overrides[get_authenticator] = _override(deps.authenticator)
    app.dependency_overrides[get_transfer_service] = _override(
        deps.transfer_service
    )
    if deps.job_repository is not None:
        app.dependency_overrides[get_job_repository] = _override(
            deps.job_repository
        )
    app.dependency_overrides[get_job_service] = _override(deps.job_service)
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
    """Execute one request against a test app within its lifespan.

    Args:
        app: FastAPI test application.
        method: HTTP method to send.
        path: Request path for the client call.
        headers: Optional request headers.
        json: Optional JSON request body.
        raise_app_exceptions: Whether to re-raise ASGI app exceptions.

    Returns:
        HTTP response returned by the test client.
    """
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
