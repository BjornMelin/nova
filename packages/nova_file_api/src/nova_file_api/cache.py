"""Caching primitives used by auth and hot-path lookups."""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from threading import RLock
from typing import Any


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
    """Build a stable versioned cache key."""
    digest = sha256(raw.encode("utf-8")).hexdigest()
    return f"{key_prefix}:{namespace}:v{key_schema_version}:{digest}"


class LocalTTLCache:
    """Small in-memory TTL cache with bounded capacity."""

    def __init__(self, *, ttl_seconds: int, max_entries: int) -> None:
        """Create a bounded local cache."""
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

    @property
    def default_ttl_seconds(self) -> int:
        """Return the cache-wide default TTL."""
        return self._ttl_seconds

    def set(
        self,
        key: str,
        value: str,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store value with optional custom TTL."""
        ttl = self._ttl_seconds if ttl_seconds is None else ttl_seconds
        now = time.monotonic()
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


class TwoTierCache:
    """Local cache used by auth and other correctness-neutral hot paths."""

    def __init__(
        self,
        *,
        local: LocalTTLCache,
        key_prefix: str = "nova",
        key_schema_version: int = 1,
        metric_incr: Callable[[str], None] | None = None,
    ) -> None:
        """Create the runtime cache wrapper."""
        self._local = local
        self._key_prefix = key_prefix
        self._key_schema_version = key_schema_version
        self._metric_incr = metric_incr

    @staticmethod
    def stable_key(namespace: str, raw: str) -> str:
        """Create a stable hash-based cache key from potentially large input."""
        digest = sha256(raw.encode("utf-8")).hexdigest()
        return f"{namespace}:{digest}"

    def namespaced_key(self, namespace: str, raw: str) -> str:
        """Build a fully namespaced versioned key."""
        return namespaced_cache_key(
            namespace=namespace,
            raw=raw,
            key_prefix=self._key_prefix,
            key_schema_version=self._key_schema_version,
        )

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Return parsed JSON object if found."""
        local_value = self._local.get(key)
        if local_value is None:
            self._incr("cache_miss_total")
            return None

        parsed, parsed_status = _parse_envelope(raw=local_value)
        if parsed_status == "ok":
            self._incr("cache_local_hit_total")
            return parsed
        if parsed_status == "expired":
            self._incr("cache_local_expired_total")
        else:
            self._incr("cache_corrupt_payload_total")
        self._local.delete(key)
        self._incr("cache_miss_total")
        return None

    async def set_json(
        self,
        key: str,
        payload: dict[str, Any],
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Serialize and store JSON payload locally."""
        encoded = _encode_envelope(
            payload=payload,
            ttl_seconds=(
                self._local.default_ttl_seconds
                if ttl_seconds is None
                else ttl_seconds
            ),
            schema_version=self._key_schema_version,
        )
        self._local.set(key, encoded, ttl_seconds=ttl_seconds)

    async def delete(self, key: str) -> None:
        """Delete a cache key."""
        self._local.delete(key)

    def _incr(self, key: str) -> None:
        callback = self._metric_incr
        if callback is not None:
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
