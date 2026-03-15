"""Reusable guarded mutation workflow helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

import structlog
from pydantic import BaseModel

from nova_file_api.errors import idempotency_conflict
from nova_file_api.idempotency import IdempotencyStore


async def run_guarded_mutation[ResponseModelT: BaseModel](
    *,
    route: str,
    scope_id: str,
    request_payload: dict[str, Any],
    idempotency_store: IdempotencyStore,
    idempotency_key: str | None,
    response_model: type[ResponseModelT],
    replay_metric: Callable[[], None],
    execute: Callable[[], Awaitable[ResponseModelT]],
    on_failure: Callable[[Exception], Awaitable[None]],
    on_success: Callable[[ResponseModelT], Awaitable[None]],
    store_response_failure_event: str,
    store_response_failure_extra: dict[str, object],
    store_response_failure_mode: Literal["log", "raise"] = "log",
) -> ResponseModelT:
    """Run a mutation with shared idempotency lifecycle and hooks."""
    claimed_idempotency = False

    if idempotency_key is not None:
        replay = await idempotency_store.load_response(
            route=route,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )
        if replay is not None:
            replay_metric()
            return response_model.model_validate(replay)

        claimed_idempotency = await idempotency_store.claim_request(
            route=route,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )
        if not claimed_idempotency:
            replay = await idempotency_store.load_response(
                route=route,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
                request_payload=request_payload,
            )
            if replay is not None:
                replay_metric()
                return response_model.model_validate(replay)
            raise idempotency_conflict(
                "idempotency request is already in progress"
            )

    try:
        response = await execute()
    except Exception as exc:
        await on_failure(exc)
        if idempotency_key is not None and claimed_idempotency:
            await idempotency_store.discard_claim(
                route=route,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
            )
        raise

    if idempotency_key is not None:
        try:
            await idempotency_store.store_response(
                route=route,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
                request_payload=request_payload,
                response_payload=response.model_dump(mode="json"),
            )
        except Exception:
            structlog.get_logger("api").exception(
                store_response_failure_event,
                **store_response_failure_extra,
            )
            if store_response_failure_mode == "raise":
                raise

    await on_success(response)
    return response
