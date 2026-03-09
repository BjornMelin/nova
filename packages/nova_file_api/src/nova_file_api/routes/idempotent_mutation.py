"""Shared idempotent mutation orchestration for route handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from nova_file_api.container import AppContainer
from nova_file_api.errors import idempotency_conflict


async def run_idempotent_mutation[TResponse: BaseModel](
    *,
    container: AppContainer,
    route: str,
    scope_id: str,
    idempotency_key: str | None,
    request_payload: dict[str, Any],
    response_model: type[TResponse],
    execute: Callable[[], Awaitable[TResponse]],
) -> TResponse:
    """Run one idempotent mutation with replay/claim/discard/store handling."""
    if idempotency_key is None:
        return await execute()

    replay = await container.idempotency_store.load_response(
        route=route,
        scope_id=scope_id,
        idempotency_key=idempotency_key,
        request_payload=request_payload,
    )
    if replay is not None:
        container.metrics.incr("idempotency_replays_total")
        return response_model.model_validate(replay)

    claimed = await container.idempotency_store.claim_request(
        route=route,
        scope_id=scope_id,
        idempotency_key=idempotency_key,
        request_payload=request_payload,
    )
    if not claimed:
        replay = await container.idempotency_store.load_response(
            route=route,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )
        if replay is not None:
            container.metrics.incr("idempotency_replays_total")
            return response_model.model_validate(replay)
        raise idempotency_conflict("idempotency request is already in progress")

    try:
        response = await execute()
    except Exception:
        await container.idempotency_store.discard_claim(
            route=route,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
        )
        raise

    await container.idempotency_store.store_response(
        route=route,
        scope_id=scope_id,
        idempotency_key=idempotency_key,
        request_payload=request_payload,
        response_payload=response.model_dump(mode="json"),
    )
    return response
