from __future__ import annotations

from typing import Any

from nova_file_api.cache import (
    LocalTTLCache,
    SharedRedisCache,
    TwoTierCache,
)
from nova_file_api.metrics import MetricsCollector
from redis.exceptions import RedisError


class _DictRedisClient:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, *, name: str, value: str, ex: int) -> None:
        del ex
        self._data[name] = value

    def ping(self) -> bool:
        return True


class _ErrorRedisClient:
    def get(self, key: str) -> str | None:
        del key
        raise RedisError("simulated read outage")

    def set(self, *, name: str, value: str, ex: int) -> None:
        del name, value, ex
        raise RedisError("simulated write outage")

    def ping(self) -> bool:
        return False


def _build_local_cache() -> LocalTTLCache:
    return LocalTTLCache(ttl_seconds=60, max_entries=128)


def _build_shared_cache(*, client: Any) -> SharedRedisCache:
    shared = SharedRedisCache(url=None)
    shared._client = client
    return shared


def test_two_tier_cache_reports_hit_and_miss_counters() -> None:
    metrics = MetricsCollector(namespace="Tests")
    shared = _build_shared_cache(client=_DictRedisClient())

    writer_cache = TwoTierCache(
        local=_build_local_cache(),
        shared=shared,
        shared_ttl_seconds=60,
        metric_incr=metrics.incr,
    )
    writer_cache.set_json("job:1", {"ok": True})
    assert writer_cache.get_json("job:1") == {"ok": True}

    reader_cache = TwoTierCache(
        local=_build_local_cache(),
        shared=shared,
        shared_ttl_seconds=60,
        metric_incr=metrics.incr,
    )
    assert reader_cache.get_json("job:1") == {"ok": True}
    # Recovery path: shared hit repopulates local cache for next read.
    assert reader_cache.get_json("job:1") == {"ok": True}
    assert reader_cache.get_json("job:missing") is None

    counters = metrics.counters_snapshot()
    assert counters["cache_local_hit_total"] == 2
    assert counters["cache_shared_hit_total"] == 1
    assert counters["cache_miss_total"] == 1


def test_two_tier_cache_reports_shared_fallback_when_redis_errors() -> None:
    metrics = MetricsCollector(namespace="Tests")
    shared = _build_shared_cache(client=_ErrorRedisClient())
    cache = TwoTierCache(
        local=_build_local_cache(),
        shared=shared,
        shared_ttl_seconds=60,
        metric_incr=metrics.incr,
    )

    assert cache.get_json("jwt:token") is None
    cache.set_json("jwt:token", {"sub": "subject-1"})

    counters = metrics.counters_snapshot()
    assert counters["cache_miss_total"] == 1
    assert counters["cache_shared_fallback_total"] == 2
