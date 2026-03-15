from __future__ import annotations

from typing import Any

import pytest
from nova_file_api.guarded_mutation import run_guarded_mutation
from pydantic import BaseModel


class _ResponseModel(BaseModel):
    value: str


class _FakeIdempotencyStore:
    def __init__(self) -> None:
        self.replay: dict[str, Any] | None = None
        self.claim_result = True
        self.stored_payload: dict[str, Any] | None = None
        self.discarded = False

    async def load_response(self, **_: Any) -> dict[str, Any] | None:
        return self.replay

    async def claim_request(self, **_: Any) -> bool:
        return self.claim_result

    async def store_response(self, **kwargs: Any) -> None:
        self.stored_payload = kwargs["response_payload"]

    async def discard_claim(self, **_: Any) -> None:
        self.discarded = True


@pytest.mark.asyncio
async def test_run_guarded_mutation_replays_response() -> None:
    store = _FakeIdempotencyStore()
    store.replay = {"value": "cached"}
    replayed: list[str] = []

    async def _execute() -> _ResponseModel:
        raise AssertionError("execute should not run on replay")

    async def _on_failure(_: Exception) -> None:
        raise AssertionError("failure hook should not run on replay")

    async def _on_success(_: _ResponseModel) -> None:
        raise AssertionError("success hook should not run on replay")

    result = await run_guarded_mutation(
        route="/v1/test",
        scope_id="scope-1",
        request_payload={"value": "x"},
        idempotency_store=store,  # type: ignore[arg-type]
        idempotency_key="abc",
        response_model=_ResponseModel,
        replay_metric=lambda: replayed.append("hit"),
        execute=_execute,
        on_failure=_on_failure,
        on_success=_on_success,
        store_response_failure_event="unused",
        store_response_failure_extra={},
    )

    assert result.value == "cached"
    assert replayed == ["hit"]


@pytest.mark.asyncio
async def test_run_guarded_mutation_discards_claim_on_failure() -> None:
    store = _FakeIdempotencyStore()
    failures: list[str] = []

    async def _execute() -> _ResponseModel:
        raise RuntimeError("boom")

    async def _on_failure(exc: Exception) -> None:
        failures.append(str(exc))

    async def _on_success(_: _ResponseModel) -> None:
        raise AssertionError("success hook should not run")

    with pytest.raises(RuntimeError, match="boom"):
        await run_guarded_mutation(
            route="/v1/test",
            scope_id="scope-1",
            request_payload={"value": "x"},
            idempotency_store=store,  # type: ignore[arg-type]
            idempotency_key="abc",
            response_model=_ResponseModel,
            replay_metric=lambda: None,
            execute=_execute,
            on_failure=_on_failure,
            on_success=_on_success,
            store_response_failure_event="unused",
            store_response_failure_extra={},
        )

    assert failures == ["boom"]
    assert store.discarded is True


@pytest.mark.asyncio
async def test_run_guarded_mutation_stores_response_and_runs_success() -> None:
    store = _FakeIdempotencyStore()
    completed: list[str] = []

    async def _execute() -> _ResponseModel:
        return _ResponseModel(value="fresh")

    async def _on_failure(_: Exception) -> None:
        raise AssertionError("failure hook should not run")

    async def _on_success(response: _ResponseModel) -> None:
        completed.append(response.value)

    result = await run_guarded_mutation(
        route="/v1/test",
        scope_id="scope-1",
        request_payload={"value": "x"},
        idempotency_store=store,  # type: ignore[arg-type]
        idempotency_key="abc",
        response_model=_ResponseModel,
        replay_metric=lambda: None,
        execute=_execute,
        on_failure=_on_failure,
        on_success=_on_success,
        store_response_failure_event="unused",
        store_response_failure_extra={},
    )

    assert result.value == "fresh"
    assert completed == ["fresh"]
    assert store.stored_payload == {"value": "fresh"}
