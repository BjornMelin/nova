"""Caching primitives used by auth and hot-path lookups."""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from redis import Redis
from redis.exceptions import RedisError


@dataclass(slots=True)
class _Entry:
    """Single cache entry with expiration metadata."""

    value: str
    expires_at: float


class LocalTTLCache:
    """Small in-memory TTL cache with bounded capacity."""

    def __init__(self, *, ttl_seconds: int, max_entries: int) -> None:
        """Create a bounded local cache.

        Args:
            ttl_seconds: Default time-to-live for entries.
            max_entries: Maximum number of entries to keep.
        """
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._data: OrderedDict[str, _Entry] = OrderedDict()

    def get(self, key: str) -> str | None:
        """Return cached string value when present and not expired."""
        now = time.monotonic()
        existing = self._data.get(key)
        if existing is None:
            return None
        if existing.expires_at <= now:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return existing.value

    def set(
        self, key: str, value: str, *, ttl_seconds: int | None = None
    ) -> None:
        """Store value with optional custom TTL."""
        now = time.monotonic()
        ttl = self._ttl_seconds if ttl_seconds is None else ttl_seconds
        self._data[key] = _Entry(value=value, expires_at=now + ttl)
        self._data.move_to_end(key)
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        while len(self._data) > self._max_entries:
            self._data.popitem(last=False)


class SharedRedisCache:
    """Best-effort Redis cache wrapper."""

    def __init__(self, url: str | None) -> None:
        """Initialize Redis client when URL is configured.

        Args:
            url: Redis connection URL, or None to disable Redis.
        """
        self._client: Redis | None = None
        if url:
            self._client = Redis.from_url(url)

    @property
    def available(self) -> bool:
        """Return True when Redis backend is configured."""
        return self._client is not None

    def get(self, key: str) -> str | None:
        """Get string value from Redis, returning None on errors/miss."""
        value, _status = self.get_with_status(key)
        return value

    def get_with_status(self, key: str) -> tuple[str | None, str]:
        """Get value and read status from shared backend.

        Returns:
            tuple[str | None, str]: Tuple of decoded value and one of
            ``disabled``, ``hit``, ``miss``, or ``error``.
        """
        if self._client is None:
            return None, "disabled"
        try:
            raw = self._client.get(key)
        except RedisError:
            return None, "error"
        if raw is None:
            return None, "miss"
        if isinstance(raw, bytes):
            return raw.decode("utf-8"), "hit"
        if isinstance(raw, str):
            return raw, "hit"
        return None, "error"

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        """Store value in Redis with TTL, swallowing backend errors."""
        self.set_with_status(key, value, ttl_seconds=ttl_seconds)

    def set_with_status(self, key: str, value: str, *, ttl_seconds: int) -> str:
        """Store value with TTL and return backend write status."""
        if self._client is None:
            return "disabled"
        try:
            self._client.set(name=key, value=value, ex=ttl_seconds)
        except RedisError:
            return "error"
        return "ok"

    def ping(self) -> bool:
        """Return backend health when configured."""
        if self._client is None:
            return True
        try:
            return bool(self._client.ping())
        except RedisError:
            return False


class TwoTierCache:
    """Two-tier cache: local first, optional shared redis second."""

    def __init__(
        self,
        *,
        local: LocalTTLCache,
        shared: SharedRedisCache,
        shared_ttl_seconds: int,
        metric_incr: Any | None = None,
    ) -> None:
        """Create cache composed of local and shared backends.

        Args:
            local: In-process local cache implementation.
            shared: Shared cache backend, typically Redis.
            shared_ttl_seconds: Default TTL for shared entries.
            metric_incr: Optional callback used for cache counters.
        """
        self._local = local
        self._shared = shared
        self._shared_ttl_seconds = shared_ttl_seconds
        self._metric_incr = metric_incr

    @staticmethod
    def stable_key(namespace: str, raw: str) -> str:
        """Create stable hash-based cache key from potentially large input."""
        digest = sha256(raw.encode("utf-8")).hexdigest()
        return f"{namespace}:{digest}"

    def get_json(self, key: str) -> dict[str, Any] | None:
        """Return parsed JSON object if found."""
        local_value = self._local.get(key)
        if local_value is not None:
            self._incr("cache_local_hit_total")
            return _parse_json(local_value)

        shared_value, status = self._shared.get_with_status(key)
        if status == "hit":
            self._incr("cache_shared_hit_total")
        elif status == "miss":
            self._incr("cache_miss_total")
        elif status == "error":
            self._incr("cache_miss_total")
            self._incr("cache_shared_fallback_total")
        elif status == "disabled":
            self._incr("cache_miss_total")
        if shared_value is None:
            return None

        self._local.set(key, shared_value)
        return _parse_json(shared_value)

    def set_json(
        self,
        key: str,
        payload: dict[str, Any],
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Serialize and store JSON payload in both tiers."""
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        self._local.set(key, encoded, ttl_seconds=ttl_seconds)
        shared_ttl = (
            self._shared_ttl_seconds if ttl_seconds is None else ttl_seconds
        )
        status = self._shared.set_with_status(
            key, encoded, ttl_seconds=shared_ttl
        )
        if status == "error":
            self._incr("cache_shared_fallback_total")

    def _incr(self, key: str) -> None:
        callback = self._metric_incr
        if callback is None:
            return
        callback(key)


def _parse_json(raw: str) -> dict[str, Any] | None:
    """Parse JSON dict payload safely."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed
