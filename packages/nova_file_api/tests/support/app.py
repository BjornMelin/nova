"""Shared test utilities for building FastAPI apps with dependency overrides."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from nova_file_api.activity import ActivityStore
from nova_file_api.app import create_app
from nova_file_api.cache import LocalTTLCache, SharedRedisCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.dependencies import (
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
        idempotency_store: Idempotency store; built from cache if None.
        idempotency_enabled: Whether idempotency is enabled when building store.
        idempotency_ttl_seconds: TTL for idempotency store when building.
        job_repository: Optional job repository override.

    Returns:
        RuntimeDeps instance ready for build_test_app.
    """
    resolved_settings = settings or Settings()
    resolved_metrics = metrics or MetricsCollector(namespace="Tests")
    if shared_cache is None or cache is None:
        shared_cache, cache = build_cache_stack()
    resolved_idempotency_store = idempotency_store or IdempotencyStore(
        cache=cache,
        enabled=idempotency_enabled,
        ttl_seconds=idempotency_ttl_seconds,
    )
    return RuntimeDeps(
        settings=resolved_settings,
        metrics=resolved_metrics,
        shared_cache=shared_cache,
        cache=cache,
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
    app = create_app()
    app.state.settings = deps.settings
    app.dependency_overrides[get_metrics] = lambda: deps.metrics
    app.dependency_overrides[get_shared_cache] = lambda: deps.shared_cache
    app.dependency_overrides[get_two_tier_cache] = lambda: deps.cache
    app.dependency_overrides[get_authenticator] = lambda: deps.authenticator
    app.dependency_overrides[get_transfer_service] = lambda: (
        deps.transfer_service
    )
    if deps.job_repository is not None:
        app.dependency_overrides[get_job_repository] = lambda: (
            deps.job_repository
        )
    app.dependency_overrides[get_job_service] = lambda: deps.job_service
    app.dependency_overrides[get_activity_store] = lambda: deps.activity_store
    app.dependency_overrides[get_idempotency_store] = lambda: (
        deps.idempotency_store
    )
    return app
