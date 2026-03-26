"""Idempotency-key handling for mutation endpoints."""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Protocol, cast
from uuid import uuid4

from botocore.exceptions import ClientError

from nova_file_api.cache import namespaced_cache_key
from nova_file_api.errors import (
    idempotency_conflict,
    idempotency_unavailable,
)

_IDEMPOTENCY_STATE_IN_PROGRESS = "in_progress"
_IDEMPOTENCY_STATE_COMMITTED = "committed"


class DynamoTable(Protocol):
    """Subset of DynamoDB table operations used by idempotency storage."""

    async def put_item(self, **kwargs: object) -> Mapping[str, object]:
        """Create or replace an item."""

    async def get_item(self, **kwargs: object) -> Mapping[str, object]:
        """Read a single item by key."""

    async def update_item(self, **kwargs: object) -> Mapping[str, object]:
        """Update an item conditionally."""

    async def delete_item(self, **kwargs: object) -> Mapping[str, object]:
        """Delete an item conditionally."""


class DynamoResource(Protocol):
    """Subset of DynamoDB resource operations used by idempotency storage."""

    def Table(self, table_name: str) -> DynamoTable | Awaitable[DynamoTable]:
        """Return table object or awaitable table object."""


def _as_dynamo_table(table: object) -> DynamoTable:
    """Validate and cast a DynamoDB table-like object."""
    invalid_methods: list[str] = []
    for method_name in ("put_item", "get_item", "update_item", "delete_item"):
        method = getattr(table, method_name, None)
        if not callable(method):
            invalid_methods.append(method_name)
    if invalid_methods:
        methods = ", ".join(invalid_methods)
        raise TypeError(
            "dynamodb resource returned an invalid table object; "
            f"missing or non-callable: {methods}"
        )
    return cast(DynamoTable, table)


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    """Ownership token for an in-progress idempotent mutation."""

    cache_key: str
    owner_token: str
    request_hash: str


@dataclass(slots=True)
class IdempotencyStore:
    """Store and replay idempotent endpoint responses."""

    table_name: str | None
    dynamodb_resource: DynamoResource | None
    enabled: bool
    ttl_seconds: int
    key_prefix: str
    key_schema_version: int
    _clock: Callable[[], float] = field(default=time.time, repr=False)
    _table: DynamoTable | None = field(default=None, init=False, repr=False)
    _table_lock: asyncio.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the lazy table resolver."""
        self._table_lock = asyncio.Lock()

    async def load_response(
        self,
        *,
        route: str,
        scope_id: str,
        idempotency_key: str,
        request_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Load stored response for a matching idempotency request."""
        if not self.enabled:
            return None

        entry = await self._read_entry(
            self._entry_cache_key(
                route=route,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
            )
        )
        if entry is None:
            return None

        expected_hash = idempotency_request_payload_hash(
            payload=request_payload
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
    ) -> IdempotencyClaim | None:
        """Claim an idempotency key for in-progress request execution."""
        if not self.enabled:
            return None

        cache_key = self._entry_cache_key(
            route=route,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
        )
        request_hash = idempotency_request_payload_hash(payload=request_payload)
        claim = IdempotencyClaim(
            cache_key=cache_key,
            owner_token=str(uuid4()),
            request_hash=request_hash,
        )

        if await self._create_claim_if_absent_or_expired(claim=claim):
            return claim

        existing = await self._read_entry(cache_key)
        if existing is None:
            return await self.claim_request(
                route=route,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
                request_payload=request_payload,
            )

        _assert_entry_request_hash(entry=existing, expected_hash=request_hash)
        state = existing.get("state")
        if state == _IDEMPOTENCY_STATE_COMMITTED:
            return None
        if state == _IDEMPOTENCY_STATE_IN_PROGRESS:
            raise idempotency_conflict(
                "idempotency request is already in progress"
            )
        raise idempotency_conflict("stored idempotency record is invalid")

    async def store_response(
        self,
        *,
        claim: IdempotencyClaim,
        response_payload: dict[str, Any],
    ) -> None:
        """Persist response for an idempotent mutation request."""
        if not self.enabled:
            return

        table = await self._resolve_table()
        now_seconds = int(self._clock())
        try:
            await table.update_item(
                Key={"idempotency_key": claim.cache_key},
                UpdateExpression=(
                    "SET #state = :committed, #response = :response, "
                    "expires_at = :expires_at"
                ),
                ConditionExpression=(
                    "attribute_exists(idempotency_key) "
                    "AND #state = :in_progress "
                    "AND request_hash = :request_hash "
                    "AND owner_token = :owner_token"
                ),
                ExpressionAttributeNames={
                    "#state": "state",
                    "#response": "response",
                },
                ExpressionAttributeValues={
                    ":committed": _IDEMPOTENCY_STATE_COMMITTED,
                    ":in_progress": _IDEMPOTENCY_STATE_IN_PROGRESS,
                    ":request_hash": claim.request_hash,
                    ":owner_token": claim.owner_token,
                    ":response": response_payload,
                    ":expires_at": now_seconds + self.ttl_seconds,
                },
            )
        except ClientError as exc:
            if _is_conditional_check_failed(exc):
                raise _idempotency_unavailable_error(
                    message="idempotency record changed before response commit"
                ) from exc
            raise _idempotency_unavailable_error(
                message="idempotency store is unavailable"
            ) from exc

    async def discard_claim(self, *, claim: IdempotencyClaim) -> None:
        """Delete in-progress idempotency claim after failed execution."""
        if not self.enabled:
            return

        table = await self._resolve_table()
        try:
            await table.delete_item(
                Key={"idempotency_key": claim.cache_key},
                ConditionExpression=(
                    "#state = :in_progress "
                    "AND request_hash = :request_hash "
                    "AND owner_token = :owner_token"
                ),
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":in_progress": _IDEMPOTENCY_STATE_IN_PROGRESS,
                    ":request_hash": claim.request_hash,
                    ":owner_token": claim.owner_token,
                },
            )
        except ClientError as exc:
            if _is_conditional_check_failed(exc):
                return
            raise _idempotency_unavailable_error(
                message="idempotency store is unavailable"
            ) from exc

    async def healthcheck(self) -> bool:
        """Return backend health when enabled."""
        if not self.enabled:
            return True
        try:
            table = await self._resolve_table()
            await table.get_item(Key={"idempotency_key": "__health_check__"})
        except Exception:
            return False
        return True

    async def _resolve_table(self) -> DynamoTable:
        if self._table is not None:
            return self._table
        if self.table_name is None or self.dynamodb_resource is None:
            raise _idempotency_unavailable_error(
                message="idempotency store is not configured"
            )
        async with self._table_lock:
            if self._table is None:
                table_obj = self.dynamodb_resource.Table(self.table_name)
                if inspect.isawaitable(table_obj):
                    table_obj = await table_obj
                self._table = _as_dynamo_table(table_obj)
        assert self._table is not None
        return self._table

    async def _read_entry(self, cache_key: str) -> dict[str, Any] | None:
        table = await self._resolve_table()
        try:
            response = await table.get_item(Key={"idempotency_key": cache_key})
        except ClientError as exc:
            raise _idempotency_unavailable_error(
                message="idempotency store is unavailable"
            ) from exc
        item = response.get("Item")
        if item is None:
            return None
        return _parse_entry(item, now_seconds=int(self._clock()))

    async def _create_claim_if_absent_or_expired(
        self,
        *,
        claim: IdempotencyClaim,
    ) -> bool:
        table = await self._resolve_table()
        now_seconds = int(self._clock())
        try:
            await table.put_item(
                Item={
                    "idempotency_key": claim.cache_key,
                    "state": _IDEMPOTENCY_STATE_IN_PROGRESS,
                    "request_hash": claim.request_hash,
                    "owner_token": claim.owner_token,
                    "expires_at": now_seconds + self.ttl_seconds,
                },
                ConditionExpression=(
                    "attribute_not_exists(idempotency_key) "
                    "OR expires_at <= :now"
                ),
                ExpressionAttributeValues={":now": now_seconds},
            )
        except ClientError as exc:
            if _is_conditional_check_failed(exc):
                return False
            raise _idempotency_unavailable_error(
                message="idempotency store is unavailable"
            ) from exc
        return True

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
            key_prefix=self.key_prefix,
            key_schema_version=self.key_schema_version,
        )


def idempotency_request_payload_hash(*, payload: dict[str, Any]) -> str:
    """SHA-256 hex digest of the JSON-normalized request payload."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _parse_entry(
    item: object,
    *,
    now_seconds: int,
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        raise idempotency_conflict("stored idempotency record is invalid")
    parsed_item = cast(dict[str, Any], item)

    expires_at = parsed_item.get("expires_at")
    if not isinstance(expires_at, (int, float)):
        raise idempotency_conflict("stored idempotency record is invalid")
    if int(expires_at) <= now_seconds:
        return None

    request_hash = parsed_item.get("request_hash")
    state = parsed_item.get("state")
    owner_token = parsed_item.get("owner_token")
    if not isinstance(request_hash, str):
        raise idempotency_conflict("stored idempotency record is invalid")
    if not isinstance(state, str):
        raise idempotency_conflict("stored idempotency record is invalid")
    if owner_token is not None and not isinstance(owner_token, str):
        raise idempotency_conflict("stored idempotency record is invalid")

    entry: dict[str, Any] = {
        "state": state,
        "request_hash": request_hash,
        "owner_token": owner_token,
        "expires_at": int(expires_at),
    }
    response_payload = parsed_item.get("response")
    if response_payload is not None:
        if not isinstance(response_payload, dict):
            raise idempotency_conflict("stored idempotency response is invalid")
        entry["response"] = response_payload
    return entry


def _assert_entry_request_hash(
    *,
    entry: dict[str, Any],
    expected_hash: str,
) -> None:
    request_hash = entry.get("request_hash")
    if not isinstance(request_hash, str):
        raise idempotency_conflict("stored idempotency record is invalid")
    if request_hash != expected_hash:
        raise idempotency_conflict(
            "idempotency key was already used with a different request",
        )


def _is_conditional_check_failed(exc: ClientError) -> bool:
    error_code = str(exc.response.get("Error", {}).get("Code", ""))
    return error_code == "ConditionalCheckFailedException"


def _idempotency_unavailable_error(*, message: str) -> Exception:
    return idempotency_unavailable(message)
