"""Idempotency-key handling for mutation endpoints."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from nova_file_api.cache import TwoTierCache
from nova_file_api.errors import idempotency_conflict

_IDEMPOTENCY_STATE_IN_PROGRESS = "in_progress"
_IDEMPOTENCY_STATE_COMMITTED = "committed"


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

    @property
    def enabled(self) -> bool:
        """Return whether idempotency checks are enabled for this store."""
        return self._enabled

    async def load_response(
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
        entry = await self._cache.get_json(cache_key)
        if entry is None:
            return None
        if not isinstance(entry, dict):
            raise idempotency_conflict("stored idempotency record is invalid")

        expected_hash = _payload_hash(payload=request_payload)
        _assert_entry_request_hash(entry=entry, expected_hash=expected_hash)

        state = entry.get("state")
        if state == _IDEMPOTENCY_STATE_IN_PROGRESS:
            raise idempotency_conflict(
                "idempotency request is already in progress"
            )
        if state != _IDEMPOTENCY_STATE_COMMITTED:
            raise idempotency_conflict("stored idempotency record is invalid")

        response_payload = entry.get("response")
        if not isinstance(response_payload, dict):
            raise idempotency_conflict("stored idempotency response is invalid")
        return response_payload

    async def claim_request(
        self,
        *,
        route: str,
        scope_id: str,
        idempotency_key: str,
        request_payload: dict[str, Any],
    ) -> bool:
        """Claim an idempotency key for in-progress request execution.

        Returns:
            ``True`` when claim is acquired and caller should execute work.
            ``False`` when an existing committed record should be replayed.
        """
        if not self._enabled:
            return False

        cache_key = self._entry_cache_key(
            route=route,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
        )
        request_hash = _payload_hash(payload=request_payload)
        claim_payload = {
            "state": _IDEMPOTENCY_STATE_IN_PROGRESS,
            "request_hash": request_hash,
        }
        created = await self._cache.set_json_if_absent(
            key=cache_key,
            payload=claim_payload,
            ttl_seconds=self._ttl_seconds,
        )
        if created:
            return True

        existing = await self._cache.get_json(cache_key)
        if existing is None:
            return await self._cache.set_json_if_absent(
                key=cache_key,
                payload=claim_payload,
                ttl_seconds=self._ttl_seconds,
            )
        if not isinstance(existing, dict):
            raise idempotency_conflict("stored idempotency record is invalid")

        _assert_entry_request_hash(entry=existing, expected_hash=request_hash)
        state = existing.get("state")
        if state == _IDEMPOTENCY_STATE_COMMITTED:
            return False
        if state == _IDEMPOTENCY_STATE_IN_PROGRESS:
            raise idempotency_conflict(
                "idempotency request is already in progress"
            )
        raise idempotency_conflict("stored idempotency record is invalid")

    async def store_response(
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
        request_hash = _payload_hash(payload=request_payload)
        existing = await self._cache.get_json(cache_key)
        if existing is not None:
            _assert_entry_request_hash(
                entry=existing,
                expected_hash=request_hash,
            )

        await self._cache.set_json(
            key=cache_key,
            payload={
                "state": _IDEMPOTENCY_STATE_COMMITTED,
                "request_hash": request_hash,
                "response": response_payload,
            },
            ttl_seconds=self._ttl_seconds,
        )

    async def discard_claim(
        self,
        *,
        route: str,
        scope_id: str,
        idempotency_key: str,
    ) -> None:
        """Delete in-progress idempotency claim after failed execution."""
        if not self._enabled:
            return
        cache_key = self._entry_cache_key(
            route=route,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
        )
        await self._cache.delete(cache_key)

    def _entry_cache_key(
        self,
        *,
        route: str,
        scope_id: str,
        idempotency_key: str,
    ) -> str:
        raw = f"{route}|{scope_id}|{idempotency_key}"
        return self._cache.namespaced_key("idempotency", raw)


def _payload_hash(*, payload: dict[str, Any]) -> str:
    """Return deterministic hash for idempotency conflict checks."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _assert_entry_request_hash(
    *,
    entry: dict[str, Any],
    expected_hash: str,
) -> None:
    seen_hash = entry.get("request_hash")
    if not isinstance(seen_hash, str):
        raise idempotency_conflict("stored idempotency record is invalid")
    if seen_hash != expected_hash:
        raise idempotency_conflict(
            "idempotency key was already used with a different request",
        )
