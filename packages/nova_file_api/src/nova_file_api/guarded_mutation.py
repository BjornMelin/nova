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
    """Run a mutation with shared idempotency lifecycle and hooks.

    Args:
        route: Canonical route path for idempotency partitioning.
        scope_id: Caller scope identifier used in idempotency keys.
        request_payload: Request payload used for idempotency hash checks.
        idempotency_store: Store handling idempotency claim/load/persist state.
        idempotency_key: Optional idempotency key for guarded execution.
        response_model: Pydantic response model for replay payload parsing.
        replay_metric: Hook emitted when replaying a stored response.
        execute: Mutation executor that performs the underlying operation.
        on_failure: Failure hook invoked when execution/storage fails.
        on_success: Success hook invoked after a successful mutation.
        store_response_failure_event: Structured log event name for store
            errors.
        store_response_failure_extra: Structured log extras for store errors.
        store_response_failure_mode: Whether store_response failures are logged
            only, or re-raised after cleanup.

    Returns:
        ResponseModelT: Fresh or replayed response model instance.

    Raises:
        FileTransferError: For idempotency conflicts.
        Exception: Errors from execute and, when configured, store_response.
    """
    logger = structlog.get_logger("api")
    claimed_idempotency = False
    idempotency_enabled = (
        idempotency_key is not None and idempotency_store.enabled
    )

    def _emit_replay_metric_best_effort() -> None:
        try:
            replay_metric()
        except Exception:
            logger.exception(
                "guarded_mutation_replay_metric_failed",
                route=route,
                scope_id=scope_id,
            )

    async def _run_failure_hook_best_effort(exc: Exception) -> None:
        try:
            await on_failure(exc)
        except Exception:
            logger.exception(
                "guarded_mutation_failure_hook_failed",
                route=route,
                scope_id=scope_id,
                error_type=type(exc).__name__,
            )

    async def _discard_claim_best_effort(*, exc: Exception) -> None:
        assert idempotency_key is not None
        try:
            await idempotency_store.discard_claim(
                route=route,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
            )
        except Exception:
            logger.exception(
                "guarded_mutation_discard_claim_failed",
                route=route,
                scope_id=scope_id,
                error_type=type(exc).__name__,
            )

    if idempotency_enabled and idempotency_key is not None:
        replay = await idempotency_store.load_response(
            route=route,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
        )
        if replay is not None:
            _emit_replay_metric_best_effort()
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
                _emit_replay_metric_best_effort()
                return response_model.model_validate(replay)
            raise idempotency_conflict(
                "idempotency request is already in progress"
            )

    try:
        response = await execute()
    except Exception as exc:
        await _run_failure_hook_best_effort(exc)
        if (
            idempotency_enabled
            and idempotency_key is not None
            and claimed_idempotency
        ):
            await _discard_claim_best_effort(exc=exc)
        raise

    if idempotency_enabled and idempotency_key is not None:
        try:
            await idempotency_store.store_response(
                route=route,
                scope_id=scope_id,
                idempotency_key=idempotency_key,
                request_payload=request_payload,
                response_payload=response.model_dump(mode="json"),
            )
        except Exception:
            logger.exception(
                store_response_failure_event,
                **store_response_failure_extra,
            )
            if store_response_failure_mode == "raise":
                raise

    try:
        await on_success(response)
    except Exception as exc:
        logger.exception(
            "guarded_mutation_success_hook_failed",
            route=route,
            scope_id=scope_id,
            error_type=type(exc).__name__,
        )
        await _run_failure_hook_best_effort(exc)
    return response
