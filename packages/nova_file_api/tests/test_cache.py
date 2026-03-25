from __future__ import annotations

import pytest
from fastapi import FastAPI
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_app
from nova_file_api.cache import (
    AsyncRedisClientProtocol,
    LocalTTLCache,
    SharedRedisCache,
    TwoTierCache,
)
from nova_file_api.config import Settings
from nova_file_api.metrics import MetricsCollector
from redis.exceptions import RedisError

from .support.app import build_runtime_deps, build_test_app
from .support.redis import MemoryRedisClient as _DictRedisClient


class _ErrorRedisClient:
    async def get(self, key: str) -> str | None:
        del key
        raise RedisError("simulated read outage")

    async def set(
        self,
        *,
        name: str,
        value: str,
        ex: int,
        nx: bool = False,
    ) -> bool:
        del name, value, ex, nx
        raise RedisError("simulated write outage")

    async def delete(self, key: str) -> int:
        del key
        raise RedisError("simulated delete outage")

    async def eval(
        self,
        script: str,
        numkeys: int,
        key: str,
        expected_value: str,
    ) -> int:
        del script, numkeys, key, expected_value
        raise RedisError("simulated delete outage")

    async def ping(self) -> bool:
        return False

    async def aclose(self) -> None:
        return None


class _TrackableAuthenticator:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


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

    def resource(self, service_name: str) -> _AsyncContextValue:
        del service_name
        return _AsyncContextValue(object())


def _build_local_cache() -> LocalTTLCache:
    return LocalTTLCache(ttl_seconds=60, max_entries=128)


def _build_shared_cache(
    *,
    client: AsyncRedisClientProtocol,
) -> SharedRedisCache:
    # Testing-only: inject a mock Redis client to bypass network initialization.
    return SharedRedisCache(url=None, client=client)


@pytest.mark.asyncio
async def test_two_tier_cache_reports_hit_and_miss_counters() -> None:
    metrics = MetricsCollector(namespace="Tests")
    shared = _build_shared_cache(client=_DictRedisClient())

    writer_cache = TwoTierCache(
        local=_build_local_cache(),
        shared=shared,
        shared_ttl_seconds=60,
        metric_incr=metrics.incr,
    )
    await writer_cache.set_json("job:1", {"ok": True})
    assert await writer_cache.get_json("job:1") == {"ok": True}

    reader_cache = TwoTierCache(
        local=_build_local_cache(),
        shared=shared,
        shared_ttl_seconds=60,
        metric_incr=metrics.incr,
    )
    assert await reader_cache.get_json("job:1") == {"ok": True}
    # Recovery path: shared hit repopulates local cache for next read.
    assert await reader_cache.get_json("job:1") == {"ok": True}
    assert await reader_cache.get_json("job:missing") is None

    counters = metrics.counters_snapshot()
    assert counters["cache_local_hit_total"] == 2
    assert counters["cache_shared_hit_total"] == 1
    assert counters["cache_miss_total"] == 1


@pytest.mark.asyncio
async def test_two_tier_cache_reports_shared_fallback_when_redis_errors() -> (
    None
):
    metrics = MetricsCollector(namespace="Tests")
    shared = _build_shared_cache(client=_ErrorRedisClient())
    cache = TwoTierCache(
        local=_build_local_cache(),
        shared=shared,
        shared_ttl_seconds=60,
        metric_incr=metrics.incr,
    )

    assert await cache.get_json("jwt:token") is None
    await cache.set_json("jwt:token", {"sub": "subject-1"})

    counters = metrics.counters_snapshot()
    assert counters["cache_miss_total"] == 1
    assert counters["cache_shared_fallback_total"] == 2


@pytest.mark.asyncio
async def test_shared_cache_delete_with_status_checks_expected_value() -> None:
    client = _DictRedisClient()
    shared = _build_shared_cache(client=client)

    created = await client.set(
        name="idempotency-key",
        value="claim-a",
        ex=60,
    )
    assert created is True

    mismatch = await shared.delete_with_status(
        "idempotency-key",
        expected_value="claim-b",
    )
    assert mismatch == "mismatch"
    assert await shared.get_with_status("idempotency-key") == (
        "claim-a",
        "hit",
    )

    deleted = await shared.delete_with_status(
        "idempotency-key",
        expected_value="claim-a",
    )
    assert deleted == "ok"
    assert await shared.get_with_status("idempotency-key") == (None, "miss")


@pytest.mark.asyncio
async def test_shared_cache_aclose_closes_bound_client() -> None:
    client = _DictRedisClient()
    shared = _build_shared_cache(client=client)

    await shared.aclose()

    assert client.closed is True
    assert shared.available is False


@pytest.mark.asyncio
async def test_shared_cache_aclose_is_noop_when_disabled() -> None:
    shared = SharedRedisCache(url=None)

    await shared.aclose()

    assert shared.available is False


@pytest.mark.asyncio
async def test_injected_app_lifespan_keeps_external_state_for_reentry() -> None:
    authenticator = _TrackableAuthenticator()
    shared_client = _DictRedisClient()
    shared_cache = _build_shared_cache(client=shared_client)
    deps = build_runtime_deps(
        authenticator=authenticator,
        transfer_service=object(),
        job_service=object(),
        activity_store=MemoryActivityStore(),
        shared_cache=shared_cache,
        cache=TwoTierCache(
            local=_build_local_cache(),
            shared=shared_cache,
            shared_ttl_seconds=60,
        ),
        idempotency_enabled=False,
    )
    app: FastAPI = build_test_app(deps)

    async with app.router.lifespan_context(app):
        assert shared_cache.available is True

    assert authenticator.closed is False
    assert shared_client.closed is False
    assert shared_cache.available is True

    async with app.router.lifespan_context(app):
        assert shared_cache.available is True


@pytest.mark.asyncio
async def test_runtime_app_lifespan_clears_runtime_state_for_reentry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import nova_file_api.app as app_module

    shared_caches: list[SharedRedisCache] = []
    authenticators: list[_TrackableAuthenticator] = []

    def _fake_initialize_runtime_state(
        app: FastAPI,
        *,
        settings: Settings,
        s3_client: object,
        dynamodb_resource: object | None = None,
        sqs_client: object | None = None,
    ) -> None:
        del settings, s3_client, dynamodb_resource, sqs_client
        authenticator = _TrackableAuthenticator()
        shared_cache = _build_shared_cache(client=_DictRedisClient())
        authenticators.append(authenticator)
        shared_caches.append(shared_cache)
        app.state.authenticator = authenticator
        app.state.shared_cache = shared_cache
        app.state.cache = TwoTierCache(
            local=_build_local_cache(),
            shared=shared_cache,
            shared_ttl_seconds=60,
        )
        app.state.idempotency_store = object()

    monkeypatch.setattr(
        app_module,
        "new_aioboto3_session",
        lambda: _FakeSession(),
    )
    monkeypatch.setattr(
        app_module,
        "initialize_runtime_state",
        _fake_initialize_runtime_state,
    )

    app = create_app(settings=Settings.model_validate({}))

    async with app.router.lifespan_context(app):
        first_shared_cache = shared_caches[0]
        first_authenticator = authenticators[0]
        assert first_shared_cache.available is True
        assert first_authenticator.closed is False

    assert first_authenticator.closed is True
    assert first_shared_cache.available is False
    assert getattr(app.state, "shared_cache", None) is None
    assert getattr(app.state, "cache", None) is None
    assert getattr(app.state, "idempotency_store", None) is None

    async with app.router.lifespan_context(app):
        second_shared_cache = shared_caches[1]
        assert second_shared_cache.available is True
        assert second_shared_cache is not first_shared_cache

    assert len(shared_caches) == 2
    assert len(authenticators) == 2


class _ExplodingAuthenticator:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True
        raise RuntimeError("simulated authenticator close failure")


class _ExplodingSharedCache(SharedRedisCache):
    def __init__(self) -> None:
        super().__init__(url=None)
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True
        raise RuntimeError("simulated shared cache close failure")


@pytest.mark.asyncio
async def test_runtime_app_lifespan_clears_runtime_state_when_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import nova_file_api.app as app_module

    authenticator = _ExplodingAuthenticator()
    shared_cache = _ExplodingSharedCache()

    def _fake_initialize_runtime_state(
        app: FastAPI,
        *,
        settings: Settings,
        s3_client: object,
        dynamodb_resource: object | None = None,
        sqs_client: object | None = None,
    ) -> None:
        del settings, s3_client, dynamodb_resource, sqs_client
        app.state.authenticator = authenticator
        app.state.shared_cache = shared_cache
        app.state.cache = TwoTierCache(
            local=_build_local_cache(),
            shared=shared_cache,
            shared_ttl_seconds=60,
        )
        app.state.idempotency_store = object()

    monkeypatch.setattr(
        app_module,
        "new_aioboto3_session",
        lambda: _FakeSession(),
    )
    monkeypatch.setattr(
        app_module,
        "initialize_runtime_state",
        _fake_initialize_runtime_state,
    )

    app = create_app(settings=Settings.model_validate({}))

    async with app.router.lifespan_context(app):
        pass

    assert authenticator.closed is True
    assert shared_cache.closed is True
    assert getattr(app.state, "authenticator", None) is None
    assert getattr(app.state, "shared_cache", None) is None
    assert getattr(app.state, "cache", None) is None
    assert getattr(app.state, "idempotency_store", None) is None
