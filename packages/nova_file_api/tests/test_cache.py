from __future__ import annotations

from typing import Any, cast

import pytest
from fastapi import FastAPI

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_managed_app
from nova_file_api.cache import LocalTTLCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.runtime import ApiRuntime, RuntimeBootstrap
from nova_runtime_support.metrics import MetricsCollector

from .support.app import build_runtime_deps, build_test_app


class _TrackableAuthenticator:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class _ExplodingAuthenticator:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True
        raise RuntimeError("simulated authenticator close failure")


class _AsyncContextValue:
    def __init__(self, value: object) -> None:
        self._value = value

    async def __aenter__(self) -> object:
        return self._value

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> bool:
        del exc_type, exc, tb
        return False


class _FakeSession:
    def client(
        self, service_name: str, *, config: object | None = None
    ) -> _AsyncContextValue:
        del service_name, config
        return _AsyncContextValue(object())

    def resource(
        self, service_name: str, *, config: object | None = None
    ) -> _AsyncContextValue:
        del service_name, config
        return _AsyncContextValue(object())


def _build_local_cache() -> LocalTTLCache:
    return LocalTTLCache(ttl_seconds=60, max_entries=128)


@pytest.mark.anyio
async def test_two_tier_cache_reports_local_hit_and_miss_counters() -> None:
    metrics = MetricsCollector(namespace="Tests")
    cache = TwoTierCache(
        local=_build_local_cache(),
        metric_incr=metrics.incr,
    )

    await cache.set_json("job:1", {"ok": True})
    assert await cache.get_json("job:1") == {"ok": True}
    assert await cache.get_json("job:missing") is None

    counters = metrics.counters_snapshot()
    assert counters["cache_local_hit_total"] == 1
    assert counters["cache_miss_total"] == 1


@pytest.mark.anyio
async def test_two_tier_cache_drops_corrupt_payloads() -> None:
    metrics = MetricsCollector(namespace="Tests")
    local = _build_local_cache()
    local.set("job:1", "not-json")
    cache = TwoTierCache(local=local, metric_incr=metrics.incr)

    assert await cache.get_json("job:1") is None

    counters = metrics.counters_snapshot()
    assert counters["cache_corrupt_payload_total"] == 1
    assert counters["cache_miss_total"] == 1


@pytest.mark.anyio
async def test_injected_app_lifespan_keeps_external_state_for_reentry() -> None:
    authenticator = _TrackableAuthenticator()
    cache = TwoTierCache(local=_build_local_cache())
    deps = build_runtime_deps(
        authenticator=authenticator,
        transfer_service=object(),
        export_service=object(),
        activity_store=MemoryActivityStore(),
        cache=cache,
        idempotency_enabled=False,
    )
    app: FastAPI = build_test_app(deps)

    async with app.router.lifespan_context(app):
        assert app.state.runtime.cache is cache

    assert authenticator.closed is False
    assert app.state.runtime.cache is cache

    async with app.router.lifespan_context(app):
        assert app.state.runtime.cache is cache


@pytest.mark.anyio
async def test_runtime_app_lifespan_clears_runtime_state_for_reentry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import nova_file_api.app as app_module

    authenticators: list[_TrackableAuthenticator] = []
    caches: list[TwoTierCache] = []

    async def _fake_bootstrap_api_runtime(
        *,
        settings: Settings,
    ) -> RuntimeBootstrap:
        del settings
        authenticator = _TrackableAuthenticator()
        cache = TwoTierCache(local=_build_local_cache())
        authenticators.append(authenticator)
        caches.append(cache)
        return RuntimeBootstrap(
            runtime=ApiRuntime(
                settings=Settings.model_validate(
                    {"IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency"}
                ),
                metrics=MetricsCollector(namespace="Tests"),
                cache=cache,
                authenticator=cast(Any, authenticator),
                transfer_service=cast(Any, object()),
                export_repository=cast(Any, object()),
                export_service=cast(Any, object()),
                activity_store=MemoryActivityStore(),
                idempotency_store=cast(Any, object()),
            )
        )

    monkeypatch.setattr(
        app_module,
        "bootstrap_api_runtime",
        _fake_bootstrap_api_runtime,
    )

    app = create_managed_app(
        settings=Settings.model_validate(
            {"IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency"}
        )
    )

    async with app.router.lifespan_context(app):
        first_cache = caches[0]
        first_authenticator = authenticators[0]
        assert app.state.runtime.cache is first_cache
        assert first_authenticator.closed is False

    async with app.router.lifespan_context(app):
        second_cache = caches[1]
        assert app.state.runtime.cache is second_cache
        assert second_cache is not first_cache

    assert len(caches) == 2
    assert len(authenticators) == 2
    assert first_authenticator.closed is True


@pytest.mark.anyio
async def test_runtime_app_lifespan_clears_runtime_state_when_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import nova_file_api.app as app_module

    authenticator = _ExplodingAuthenticator()

    async def _fake_bootstrap_api_runtime(
        *,
        settings: Settings,
    ) -> RuntimeBootstrap:
        del settings
        return RuntimeBootstrap(
            runtime=ApiRuntime(
                settings=Settings.model_validate(
                    {"IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency"}
                ),
                metrics=MetricsCollector(namespace="Tests"),
                cache=TwoTierCache(local=_build_local_cache()),
                authenticator=cast(Any, authenticator),
                transfer_service=cast(Any, object()),
                export_repository=cast(Any, object()),
                export_service=cast(Any, object()),
                activity_store=MemoryActivityStore(),
                idempotency_store=cast(Any, object()),
            )
        )

    monkeypatch.setattr(
        app_module,
        "bootstrap_api_runtime",
        _fake_bootstrap_api_runtime,
    )

    app = create_managed_app(
        settings=Settings.model_validate(
            {"IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency"}
        )
    )

    async with app.router.lifespan_context(app):
        pass

    assert authenticator.closed is True
    assert getattr(app.state, "runtime", None) is None


@pytest.mark.anyio
async def test_runtime_app_lifespan_rejects_partial_appconfig_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_managed_app(
        settings=Settings.model_validate(
            {
                "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
                "FILE_TRANSFER_POLICY_APPCONFIG_APPLICATION": "app",
                "FILE_TRANSFER_POLICY_APPCONFIG_PROFILE": "profile",
            }
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "Transfer policy AppConfig settings must be configured together"
        ),
    ):
        async with app.router.lifespan_context(app):
            pass
