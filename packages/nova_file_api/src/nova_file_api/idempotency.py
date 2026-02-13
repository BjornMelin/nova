"""Idempotency-key handling for mutation endpoints."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from nova_file_api.cache import TwoTierCache
from nova_file_api.errors import idempotency_conflict


class IdempotencyStore:
    """Store and replay idempotent endpoint responses."""

    def __init__(
        self,
        *,
        cache: TwoTierCache,
        enabled: bool,
        ttl_seconds: int,
    ) -> None:
        """Initialize idempotency storage.

        Args:
            cache: Cache backend used for idempotency entries.
            enabled: Whether idempotency checks are active.
            ttl_seconds: TTL for stored idempotent responses.
        """
        self._cache = cache
        self._enabled = enabled
        self._ttl_seconds = ttl_seconds

    def load_response(
        self,
        *,
        route: str,
        scope_id: str,
        idempotency_key: str,
        request_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Load stored response for a matching idempotency request.

        Args:
            route: Request route key.
            scope_id: Caller scope ID.
            idempotency_key: Client-provided idempotency key.
            request_payload: Request payload for conflict detection.

        Returns:
            Stored response payload when a compatible prior request exists.

        Raises:
            FileTransferError: If the same key was used with a different
                payload.
        """
        if not self._enabled:
            return None

        cache_key = self._entry_cache_key(
            route=route,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
        )
        entry = self._cache.get_json(cache_key)
        if entry is None:
            return None

        expected_hash = _payload_hash(request_payload)
        seen_hash = entry.get("request_hash")
        if not isinstance(seen_hash, str):
            raise idempotency_conflict("stored idempotency record is invalid")
        if seen_hash != expected_hash:
            raise idempotency_conflict(
                "idempotency key was already used with a different request",
            )

        response_payload = entry.get("response")
        if not isinstance(response_payload, dict):
            raise idempotency_conflict("stored idempotency response is invalid")
        return response_payload

    def store_response(
        self,
        *,
        route: str,
        scope_id: str,
        idempotency_key: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
    ) -> None:
        """Persist response for an idempotent mutation request.

        Args:
            route: Request route key.
            scope_id: Caller scope ID.
            idempotency_key: Client-provided idempotency key.
            request_payload: Request payload that produced the response.
            response_payload: Response payload to replay on retries.
        """
        if not self._enabled:
            return

        cache_key = self._entry_cache_key(
            route=route,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
        )
        self._cache.set_json(
            key=cache_key,
            payload={
                "request_hash": _payload_hash(request_payload),
                "response": response_payload,
            },
            ttl_seconds=self._ttl_seconds,
        )

    def _entry_cache_key(
        self,
        *,
        route: str,
        scope_id: str,
        idempotency_key: str,
    ) -> str:
        raw = f"{route}|{scope_id}|{idempotency_key}"
        return TwoTierCache.stable_key("idempotency", raw)


def _payload_hash(payload: dict[str, Any]) -> str:
    """Return deterministic hash for idempotency conflict checks."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()
