"""Caching primitives used by auth and hot-path lookups."""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from inspect import isawaitable
from threading import RLock
from typing import Any, cast

from redis.asyncio import Redis
from redis.backoff import ExponentialWithJitterBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

_DELETE_IF_VALUE_MATCHES_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
end
return 0
"""


@dataclass(slots=True)
class _Entry:
    """Single cache entry with expiration metadata."""

    value: str
    expires_at: float


def namespaced_cache_key(
    *,
    namespace: str,
    raw: str,
    key_prefix: str,
    key_schema_version: int,
) -> str:
    """Build a stable versioned cache key for shared storage.

    Args:
        namespace: Cache namespace used to partition keyspace.
        raw: Raw cache input to hash.
        key_prefix: Global key prefix shared by the runtime.
        key_schema_version: Version marker for schema evolution.

    Returns:
        str: A stable versioned cache key.
    """
    digest = sha256(raw.encode("utf-8")).hexdigest()
    return f"{key_prefix}:{namespace}:v{key_schema_version}:{digest}"


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
        self._lock = RLock()

    def get(self, key: str) -> str | None:
        """Return cached string value when present and not expired."""
        now = time.monotonic()
        with self._lock:
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
        with self._lock:
            self._data[key] = _Entry(value=value, expires_at=now + ttl)
            self._data.move_to_end(key)
            self._evict_if_needed()

    def delete(self, key: str) -> None:
        """Delete a local cache key if it exists."""
        with self._lock:
            self._data.pop(key, None)

    def _evict_if_needed(self) -> None:
        while len(self._data) > self._max_entries:
            self._data.popitem(last=False)


class SharedRedisCache:
    """Best-effort async Redis cache wrapper."""

    def __init__(
        self,
        *,
        url: str | None,
        max_connections: int = 64,
        socket_timeout_seconds: float = 0.5,
        socket_connect_timeout_seconds: float = 0.5,
        health_check_interval_seconds: int = 30,
        retry_base_seconds: float = 0.05,
        retry_cap_seconds: float = 0.5,
        retry_attempts: int = 2,
        decode_responses: bool = False,
        protocol: int = 2,
        client: Redis | None = None,
    ) -> None:
        """Initialize Redis client when URL is configured.

        When ``client`` is provided, it is used as the backend and ``url`` is
        ignored. This supports tests and other explicit wiring.
        """
        self._client: Redis | None = None
        if client is not None:
            self._client = client
            return
        if not url:
            return

        retry = Retry(
            backoff=ExponentialWithJitterBackoff(
                base=retry_base_seconds,
                cap=retry_cap_seconds,
            ),
            retries=retry_attempts,
        )
        self._client = Redis.from_url(
            url,
            max_connections=max_connections,
            socket_timeout=socket_timeout_seconds,
            socket_connect_timeout=socket_connect_timeout_seconds,
            health_check_interval=health_check_interval_seconds,
            retry=retry,
            decode_responses=decode_responses,
            protocol=protocol,
        )

    @property
    def available(self) -> bool:
        """Return True when Redis backend is configured."""
        return self._client is not None

    def bind_redis_client(self, client: Redis) -> None:
        """Replace the async Redis backend (tests / explicit wiring)."""
        self._client = client

    async def get_with_status(self, key: str) -> tuple[str | None, str]:
        """Get value and read status from shared backend.

        Returns:
            Tuple of decoded value and one of
            ``disabled``, ``hit``, ``miss``, or ``error``.
        """
        if self._client is None:
            return None, "disabled"
        try:
            raw = await self._client.get(key)
        except RedisError:
            return None, "error"

        if raw is None:
            return None, "miss"
        if isinstance(raw, bytes):
            try:
                return raw.decode("utf-8"), "hit"
            except UnicodeDecodeError:
                return None, "error"
        if isinstance(raw, str):
            return raw, "hit"
        return None, "error"

    async def set_with_status(
        self,
        key: str,
        value: str,
        *,
        ttl_seconds: int,
    ) -> str:
        """Store value with TTL and return backend write status."""
        if self._client is None:
            return "disabled"
        try:
            await self._client.set(name=key, value=value, ex=ttl_seconds)
        except RedisError:
            return "error"
        return "ok"

    async def set_if_absent_with_status(
        self,
        key: str,
        value: str,
        *,
        ttl_seconds: int,
    ) -> str:
        """Store value iff absent and return write status."""
        if self._client is None:
            return "disabled"
        try:
            created = await self._client.set(
                name=key,
                value=value,
                ex=ttl_seconds,
                nx=True,
            )
        except RedisError:
            return "error"
        return "created" if bool(created) else "exists"

    async def delete_with_status(
        self,
        key: str,
        *,
        expected_value: str | None = None,
    ) -> str:
        """Delete key and return backend status.

        Returns one of ``disabled``, ``ok``, ``mismatch``, or ``error``.
        ``mismatch`` is used only when ``expected_value`` is provided and the
        shared key is missing or no longer owned by the caller.
        """
        if self._client is None:
            return "disabled"
        try:
            if expected_value is None:
                await self._client.delete(key)
                return "ok"
            maybe_deleted = self._client.eval(
                _DELETE_IF_VALUE_MATCHES_LUA,
                1,
                key,
                expected_value,
            )
            deleted = (
                await maybe_deleted
                if isawaitable(maybe_deleted)
                else maybe_deleted
            )
        except RedisError:
            return "error"
        deleted_count = cast(int, deleted)
        return "ok" if deleted_count == 1 else "mismatch"

    async def ping(self) -> bool:
        """Return backend health when configured."""
        if self._client is None:
            return True
        try:
            ping_result = self._client.ping()
            if isinstance(ping_result, bool):
                return ping_result
            return bool(await ping_result)
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
        key_prefix: str = "nova",
        key_schema_version: int = 1,
        metric_incr: Callable[[str], None] | None = None,
    ) -> None:
        """Create cache composed of local and shared backends."""
        self._local = local
        self._shared = shared
        self._shared_ttl_seconds = shared_ttl_seconds
        self._key_prefix = key_prefix
        self._key_schema_version = key_schema_version
        self._metric_incr = metric_incr

    @staticmethod
    def stable_key(namespace: str, raw: str) -> str:
        """Create stable hash-based cache key from potentially large input."""
        digest = sha256(raw.encode("utf-8")).hexdigest()
        return f"{namespace}:{digest}"

    def namespaced_key(self, namespace: str, raw: str) -> str:
        """Build a fully namespaced versioned key for shared cache usage."""
        return namespaced_cache_key(
            namespace=namespace,
            raw=raw,
            key_prefix=self._key_prefix,
            key_schema_version=self._key_schema_version,
        )

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Return parsed JSON object if found."""
        local_value = self._local.get(key)
        if local_value is not None:
            parsed, parsed_status = _parse_envelope(raw=local_value)
            if parsed_status == "ok":
                self._incr("cache_local_hit_total")
                return parsed
            if parsed_status == "expired":
                self._incr("cache_local_expired_total")
            else:
                self._incr("cache_corrupt_payload_total")
            self._local.delete(key)

        shared_value, status = await self._shared.get_with_status(key)
        if status == "hit":
            if shared_value is None:
                self._incr("cache_miss_total")
                return None
            parsed, parsed_status = _parse_envelope(raw=shared_value)
            if parsed_status == "ok" and parsed is not None:
                self._incr("cache_shared_hit_total")
                self._local.set(key, shared_value)
                return parsed
            if parsed_status == "expired":
                self._incr("cache_shared_expired_total")
            else:
                self._incr("cache_corrupt_payload_total")
            self._incr("cache_miss_total")
            return None
        if status == "miss":
            self._incr("cache_miss_total")
            return None
        if status == "error":
            self._incr("cache_miss_total")
            self._incr("cache_shared_fallback_total")
            self._incr("cache_get_error_total")
            return None

        self._incr("cache_miss_total")
        return None

    async def set_json(
        self,
        key: str,
        payload: dict[str, Any],
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Serialize and store JSON payload in both tiers."""
        ttl = self._shared_ttl_seconds if ttl_seconds is None else ttl_seconds
        encoded = _encode_envelope(
            payload=payload,
            ttl_seconds=ttl,
            schema_version=self._key_schema_version,
        )

        self._local.set(key, encoded, ttl_seconds=ttl)
        status = await self._shared.set_with_status(
            key,
            encoded,
            ttl_seconds=ttl,
        )
        if status == "error":
            self._incr("cache_shared_fallback_total")
            self._incr("cache_set_error_total")

    async def set_json_if_absent(
        self,
        *,
        key: str,
        payload: dict[str, Any],
        ttl_seconds: int,
    ) -> bool:
        """Atomically set key if absent; local fallback is best effort."""
        encoded = _encode_envelope(
            payload=payload,
            ttl_seconds=ttl_seconds,
            schema_version=self._key_schema_version,
        )

        status = await self._shared.set_if_absent_with_status(
            key,
            encoded,
            ttl_seconds=ttl_seconds,
        )
        if status == "created":
            self._local.set(key, encoded, ttl_seconds=ttl_seconds)
            return True
        if status == "exists":
            return False
        if status == "error":
            self._incr("cache_shared_fallback_total")
            self._incr("cache_set_error_total")

        local_value = self._local.get(key)
        if local_value is not None:
            return False
        self._local.set(key, encoded, ttl_seconds=ttl_seconds)
        return True

    async def delete(self, key: str) -> None:
        """Delete cache key from local and shared tiers."""
        self._local.delete(key)
        status = await self._shared.delete_with_status(key)
        if status == "error":
            self._incr("cache_shared_fallback_total")

    def _incr(self, key: str) -> None:
        callback = self._metric_incr
        if callback is None:
            return
        callback(key)


def _encode_envelope(
    *,
    payload: dict[str, Any],
    ttl_seconds: int,
    schema_version: int,
) -> str:
    now_seconds = int(time.time())
    envelope = {
        "schema_version": schema_version,
        "written_at": now_seconds,
        "expires_at": now_seconds + ttl_seconds,
        "payload": payload,
    }
    return json.dumps(envelope, separators=(",", ":"), sort_keys=True)


def _parse_envelope(raw: str | None) -> tuple[dict[str, Any] | None, str]:
    """Parse cache envelope safely."""
    if raw is None:
        return None, "missing"

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None, "invalid"

    if not isinstance(parsed, dict):
        return None, "invalid"

    schema_version = parsed.get("schema_version")
    expires_at = parsed.get("expires_at")
    payload = parsed.get("payload")
    if not isinstance(schema_version, int):
        return None, "invalid"
    if not isinstance(expires_at, (int, float)):
        return None, "invalid"
    if not isinstance(payload, dict):
        return None, "invalid"
    if int(time.time()) >= int(expires_at):
        return None, "expired"
    return payload, "ok"
