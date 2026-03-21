"""Idempotency-key handling for mutation endpoints."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from nova_file_api.cache import SharedRedisCache, namespaced_cache_key
from nova_file_api.errors import (
    idempotency_conflict,
    idempotency_unavailable,
)

_IDEMPOTENCY_STATE_IN_PROGRESS = "in_progress"
_IDEMPOTENCY_STATE_COMMITTED = "committed"


class IdempotencyStore:
    """Store and replay idempotent endpoint responses."""

    def __init__(
        self,
        *,
        shared_cache: SharedRedisCache,
        enabled: bool,
        ttl_seconds: int,
        key_prefix: str,
        key_schema_version: int,
    ) -> None:
        """Initialize idempotency storage.

        Args:
            shared_cache: Shared claim/persist backend for idempotency entries.
            enabled: Whether idempotency checks are active.
            ttl_seconds: TTL for stored idempotent responses.
            key_prefix: Shared cache namespace prefix.
            key_schema_version: Shared cache key schema version.
        """
        self._shared_cache = shared_cache
        self._enabled = enabled
        self._ttl_seconds = ttl_seconds
        self._key_prefix = key_prefix
        self._key_schema_version = key_schema_version

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
        entry = await self._read_entry(cache_key)
        if entry is None:
            return None
        if not isinstance(entry, dict):
            raise idempotency_conflict("stored idempotency record is invalid")

        expected_hash = idempotency_request_payload_hash(
            payload=request_payload,
        )
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
        request_hash = idempotency_request_payload_hash(
            payload=request_payload,
        )
        claim_payload = {
            "state": _IDEMPOTENCY_STATE_IN_PROGRESS,
            "request_hash": request_hash,
        }
        created = await self._write_entry_if_absent(
            cache_key=cache_key,
            payload=claim_payload,
        )
        if created:
            return True

        existing = await self._read_entry(cache_key)
        if existing is None:
            raise idempotency_conflict("stored idempotency record is invalid")
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
        request_hash = idempotency_request_payload_hash(
            payload=request_payload,
        )
        existing = await self._read_entry(cache_key)
        if existing is not None:
            _assert_entry_request_hash(
                entry=existing,
                expected_hash=request_hash,
            )

        await self._write_entry(
            cache_key=cache_key,
            payload={
                "state": _IDEMPOTENCY_STATE_COMMITTED,
                "request_hash": request_hash,
                "response": response_payload,
            },
        )

    async def discard_claim(
        self,
        *,
        route: str,
        scope_id: str,
        idempotency_key: str,
        request_payload: dict[str, Any],
    ) -> None:
        """Delete in-progress idempotency claim after failed execution."""
        if not self._enabled:
            return
        cache_key = self._entry_cache_key(
            route=route,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
        )
        request_hash = idempotency_request_payload_hash(
            payload=request_payload,
        )
        expected_entry = _serialize_entry(
            {
                "state": _IDEMPOTENCY_STATE_IN_PROGRESS,
                "request_hash": request_hash,
            }
        )
        status = await self._shared_cache.delete_with_status(
            cache_key,
            expected_value=expected_entry,
        )
        if status in {"ok", "mismatch"}:
            return
        raise _idempotency_unavailable_error(status=status)

    def _entry_cache_key(
        self,
        *,
        route: str,
        scope_id: str,
        idempotency_key: str,
    ) -> str:
        raw = f"{route}|{scope_id}|{idempotency_key}"
        return namespaced_cache_key(
            namespace="idempotency",
            raw=raw,
            key_prefix=self._key_prefix,
            key_schema_version=self._key_schema_version,
        )

    async def _read_entry(self, cache_key: str) -> dict[str, Any] | None:
        raw_value, status = await self._shared_cache.get_with_status(cache_key)
        if status == "miss":
            return None
        if status == "hit" and raw_value is not None:
            return _parse_entry(raw_value)
        raise _idempotency_unavailable_error(status=status)

    async def _write_entry_if_absent(
        self,
        *,
        cache_key: str,
        payload: dict[str, Any],
    ) -> bool:
        status = await self._shared_cache.set_if_absent_with_status(
            cache_key,
            _serialize_entry(payload),
            ttl_seconds=self._ttl_seconds,
        )
        if status == "created":
            return True
        if status == "exists":
            return False
        raise _idempotency_unavailable_error(status=status)

    async def _write_entry(
        self,
        *,
        cache_key: str,
        payload: dict[str, Any],
    ) -> None:
        status = await self._shared_cache.set_with_status(
            cache_key,
            _serialize_entry(payload),
            ttl_seconds=self._ttl_seconds,
        )
        if status == "ok":
            return
        raise _idempotency_unavailable_error(status=status)


def idempotency_request_payload_hash(*, payload: dict[str, Any]) -> str:
    """SHA-256 hex digest of the JSON-normalized request payload.

    Args:
        payload: Request payload to normalize and hash.

    Returns:
        SHA-256 hex digest string.
    """
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _serialize_entry(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _parse_entry(raw_value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise idempotency_conflict(
            "stored idempotency record is invalid"
        ) from exc
    if not isinstance(parsed, dict):
        raise idempotency_conflict("stored idempotency record is invalid")
    return parsed


def _idempotency_unavailable_error(*, status: str) -> Exception:
    if status == "disabled":
        message = "shared idempotency store is not configured"
    else:
        message = "shared idempotency store is unavailable"
    return idempotency_unavailable(message)


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
