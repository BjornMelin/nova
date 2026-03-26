from __future__ import annotations

from typing import Any

import pytest
from nova_file_api.guarded_mutation import run_guarded_mutation
from nova_file_api.idempotency import IdempotencyClaim, IdempotencyStore
from pydantic import BaseModel


class _ResponseModel(BaseModel):
    value: str


class _FakeIdempotencyStore(IdempotencyStore):
    def __init__(self) -> None:
        owner_value = "claim-owner"
        self._enabled = True
        self.replay: dict[str, Any] | None = None
        self.claim_result: IdempotencyClaim | None = IdempotencyClaim(
            cache_key="cache-key",
            owner_token=owner_value,
            request_hash="request-hash",
        )
        self.stored_payload: dict[str, Any] | None = None
        self.stored_claim: IdempotencyClaim | None = None
        self.discard_calls = 0
        self.discarded_claims: list[IdempotencyClaim] = []
        self.raise_on_store = False
        self.raise_on_discard = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    async def load_response(self, **_: Any) -> dict[str, Any] | None:
        return self.replay

    async def claim_request(self, **_: Any) -> IdempotencyClaim | None:
        return self.claim_result

    async def store_response(self, **kwargs: Any) -> None:
        self.stored_claim = kwargs["claim"]
        if self.raise_on_store:
            raise RuntimeError("store failed")
        self.stored_payload = kwargs["response_payload"]

    async def discard_claim(self, **kwargs: Any) -> None:
        if self.raise_on_discard:
            raise RuntimeError("discard failed")
        self.discarded_claims.append(kwargs["claim"])
        self.discard_calls += 1


@pytest.mark.anyio
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
        idempotency_store=store,
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


@pytest.mark.anyio
async def test_replay_metric_failure_is_best_effort() -> None:
    store = _FakeIdempotencyStore()
    store.replay = {"value": "cached"}

    async def _execute() -> _ResponseModel:
        raise AssertionError("execute should not run on replay")

    async def _on_failure(_: Exception) -> None:
        raise AssertionError("failure hook should not run on replay")

    async def _on_success(_: _ResponseModel) -> None:
        raise AssertionError("success hook should not run on replay")

    def _raise_metric_failure() -> None:
        raise RuntimeError("metric failed")

    result = await run_guarded_mutation(
        route="/v1/test",
        scope_id="scope-1",
        request_payload={"value": "x"},
        idempotency_store=store,
        idempotency_key="abc",
        response_model=_ResponseModel,
        replay_metric=_raise_metric_failure,
        execute=_execute,
        on_failure=_on_failure,
        on_success=_on_success,
        store_response_failure_event="unused",
        store_response_failure_extra={},
    )

    assert result.value == "cached"


@pytest.mark.anyio
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
            idempotency_store=store,
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
    assert store.discard_calls == 1
    assert store.discarded_claims == [store.claim_result]


@pytest.mark.anyio
async def test_discard_claim_when_failure_hook_raises() -> None:
    store = _FakeIdempotencyStore()

    async def _execute() -> _ResponseModel:
        raise RuntimeError("boom")

    async def _on_failure(_: Exception) -> None:
        raise RuntimeError("hook failed")

    async def _on_success(_: _ResponseModel) -> None:
        raise AssertionError("success hook should not run")

    with pytest.raises(RuntimeError, match="boom"):
        await run_guarded_mutation(
            route="/v1/test",
            scope_id="scope-1",
            request_payload={"value": "x"},
            idempotency_store=store,
            idempotency_key="abc",
            response_model=_ResponseModel,
            replay_metric=lambda: None,
            execute=_execute,
            on_failure=_on_failure,
            on_success=_on_success,
            store_response_failure_event="unused",
            store_response_failure_extra={},
        )

    assert store.discard_calls == 1
    assert store.discarded_claims == [store.claim_result]


@pytest.mark.anyio
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
        idempotency_store=store,
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
    assert store.stored_claim == store.claim_result


@pytest.mark.anyio
async def test_run_guarded_mutation_disabled_store_skips_claim_flow() -> None:
    store = _FakeIdempotencyStore()
    store.enabled = False
    store.claim_result = None
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
        idempotency_store=store,
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
    assert store.stored_payload is None


@pytest.mark.anyio
async def test_claim_false_without_replay_conflicts() -> None:
    store = _FakeIdempotencyStore()
    store.claim_result = None
    failures: list[str] = []
    successes: list[str] = []

    async def _execute() -> _ResponseModel:
        raise AssertionError("execute should not run on idempotency conflict")

    async def _on_failure(exc: Exception) -> None:
        failures.append(str(exc))

    async def _on_success(response: _ResponseModel) -> None:
        successes.append(response.value)

    with pytest.raises(Exception, match="already in progress"):
        await run_guarded_mutation(
            route="/v1/test",
            scope_id="scope-1",
            request_payload={"value": "x"},
            idempotency_store=store,
            idempotency_key="abc",
            response_model=_ResponseModel,
            replay_metric=lambda: None,
            execute=_execute,
            on_failure=_on_failure,
            on_success=_on_success,
            store_response_failure_event="unused",
            store_response_failure_extra={},
        )

    assert failures == []
    assert successes == []
    assert store.discard_calls == 0


@pytest.mark.anyio
async def test_run_guarded_mutation_store_failure_raise_preserves_claim() -> (
    None
):
    store = _FakeIdempotencyStore()
    store.raise_on_store = True
    failures: list[str] = []

    async def _execute() -> _ResponseModel:
        return _ResponseModel(value="fresh")

    async def _on_failure(exc: Exception) -> None:
        failures.append(str(exc))

    async def _on_success(_: _ResponseModel) -> None:
        raise AssertionError("success hook should not run")

    with pytest.raises(RuntimeError, match="store failed"):
        await run_guarded_mutation(
            route="/v1/test",
            scope_id="scope-1",
            request_payload={"value": "x"},
            idempotency_store=store,
            idempotency_key="abc",
            response_model=_ResponseModel,
            replay_metric=lambda: None,
            execute=_execute,
            on_failure=_on_failure,
            on_success=_on_success,
            store_response_failure_event="unused",
            store_response_failure_extra={},
            store_response_failure_mode="raise",
        )

    assert failures == []
    assert store.discard_calls == 0
    assert store.stored_claim == store.claim_result
