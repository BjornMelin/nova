from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import override
from unittest.mock import AsyncMock, Mock

import nova_file_api.idempotency as idempotency_module
import pytest
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.cache import SharedRedisCache, namespaced_cache_key
from nova_file_api.config import Settings
from nova_file_api.dependencies import (
    build_idempotency_store,
    build_two_tier_cache,
)
from nova_file_api.errors import queue_unavailable
from nova_file_api.idempotency import (
    IdempotencyStore,
    idempotency_request_payload_hash,
)
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    EnqueueJobResponse,
    InitiateUploadResponse,
    JobRecord,
    JobStatus,
    Principal,
    UploadStrategy,
)
from redis.exceptions import RedisError

from .support.app import (
    RuntimeDeps,
    build_cache_stack,
    build_runtime_deps,
    build_test_app,
    request_app,
)
from .support.redis import MemoryRedisClient as _DictRedisClient


class _StubAuthenticator:
    async def authenticate(
        self,
        *,
        token: str | None,
    ) -> Principal:
        del token
        return Principal(
            subject="user-1",
            scope_id="scope-1",
            tenant_id=None,
            scopes=(),
            permissions=("metrics:read",),
        )


class _StubJobService:
    calls: int

    def __init__(self) -> None:
        self.calls = 0

    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, object],
        scope_id: str,
    ) -> JobRecord:
        self.calls += 1
        now = datetime.now(tz=UTC)
        return JobRecord(
            job_id=f"job-{self.calls}",
            job_type=job_type,
            scope_id=scope_id,
            status=JobStatus.PENDING,
            payload=payload,
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
        )

    async def get(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise RuntimeError("not used by this test")

    async def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise RuntimeError("not used by this test")


class _StubTransferService:
    calls: int

    def __init__(self) -> None:
        self.calls = 0

    async def initiate_upload(
        self,
        payload: object,
        principal: Principal,
    ) -> InitiateUploadResponse:
        del payload, principal
        self.calls += 1
        return InitiateUploadResponse(
            strategy=UploadStrategy.SINGLE,
            bucket="bucket-a",
            key=f"uploads/scope-1/object-{self.calls}",
            expires_in_seconds=900,
            url=f"https://example.local/upload/{self.calls}",
        )


class _FailFirstEnqueueJobService(_StubJobService):
    calls: int

    @override
    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, object],
        scope_id: str,
    ) -> JobRecord:
        if self.calls == 0:
            self.calls += 1
            raise queue_unavailable(
                "job enqueue failed because queue unavailable"
            )
        return await super().enqueue(
            job_type=job_type,
            payload=payload,
            scope_id=scope_id,
        )


class _ErrorRedisClient:
    async def get(self, key: str) -> str | None:
        del key
        raise RedisError("simulated read outage")

    async def set(
        self,
        *,
        name: str,
        value: str,
        ex: int,
        nx: bool = False,
    ) -> bool:
        del name, value, ex, nx
        raise RedisError("simulated write outage")

    async def delete(self, key: str) -> int:
        del key
        raise RedisError("simulated delete outage")

    async def eval(
        self,
        script: str,
        numkeys: int,
        key: str,
        expected_value: str,
    ) -> int:
        del script, numkeys, key, expected_value
        raise RedisError("simulated delete outage")

    async def ping(self) -> bool:
        return False


class _ClaimOnlyRedisClient:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(
        self,
        *,
        name: str,
        value: str,
        ex: int,
        nx: bool = False,
    ) -> bool:
        del ex
        if nx:
            if name in self._data:
                return False
            self._data[name] = value
            return True
        raise RedisError("simulated commit outage")

    async def delete(self, key: str) -> int:
        return 1 if self._data.pop(key, None) is not None else 0

    async def eval(
        self,
        script: str,
        numkeys: int,
        key: str,
        expected_value: str,
    ) -> int:
        del script, numkeys
        if self._data.get(key) != expected_value:
            return 0
        return await self.delete(key)

    async def ping(self) -> bool:
        return True


def _shared_cache_with_client(client: object) -> SharedRedisCache:
    shared_cache = SharedRedisCache(url=None)
    shared_cache._client = client  # type: ignore[assignment]
    return shared_cache


def _replace_shared_cache(
    *,
    deps: RuntimeDeps,
    shared_cache: SharedRedisCache,
) -> None:
    """Rebind cache and idempotency store to a replacement shared cache."""
    deps.shared_cache = shared_cache
    deps.cache = build_two_tier_cache(
        settings=deps.settings,
        metrics=deps.metrics,
        shared_cache=shared_cache,
    )
    deps.idempotency_store = build_idempotency_store(
        settings=deps.settings,
        shared_cache=shared_cache,
    )


def _build_deps(
    *,
    idempotency_enabled: bool = True,
    use_in_memory_shared_cache: bool = True,
) -> tuple[RuntimeDeps, _StubTransferService, _StubJobService]:
    settings = Settings.model_validate({})
    settings.idempotency_enabled = idempotency_enabled
    settings.jobs_enabled = True
    metrics = MetricsCollector(namespace="Tests")
    shared, cache = build_cache_stack()
    transfer_service = _StubTransferService()
    job_service = _StubJobService()
    deps = build_runtime_deps(
        settings=settings,
        metrics=metrics,
        shared_cache=shared,
        cache=cache,
        authenticator=_StubAuthenticator(),
        transfer_service=transfer_service,
        job_service=job_service,
        activity_store=MemoryActivityStore(),
        idempotency_enabled=idempotency_enabled,
        use_in_memory_shared_cache=use_in_memory_shared_cache,
    )
    return deps, transfer_service, job_service


@pytest.mark.asyncio
async def test_v1_initiate_allows_missing_idempotency_key_when_enabled() -> (
    None
):
    """Verify `/v1/transfers/uploads/initiate` accepts requests without key."""
    deps, transfer_service, _job_service = _build_deps()
    app = build_test_app(deps)
    response = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        json={
            "filename": "sample.csv",
            "size_bytes": 42,
            "content_type": "text/csv",
        },
    )
    assert response.status_code == 200
    assert transfer_service.calls == 1


@pytest.mark.asyncio
async def test_v1_initiate_replays_response_for_same_idempotency_key() -> None:
    """Verify same initiate key+payload replays the cached response."""
    deps, transfer_service, _job_service = _build_deps()
    app = build_test_app(deps)
    first = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        headers={"Idempotency-Key": "upload-key-1"},
        json={
            "filename": "sample.csv",
            "size_bytes": 42,
            "content_type": "text/csv",
        },
    )
    second = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        headers={"Idempotency-Key": "upload-key-1"},
        json={
            "filename": "sample.csv",
            "size_bytes": 42,
            "content_type": "text/csv",
        },
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert transfer_service.calls == 1


@pytest.mark.asyncio
async def test_v1_initiate_rejects_key_reuse_with_different_payload() -> None:
    """Verify key reuse with different initiate payload returns conflict."""
    deps, transfer_service, _job_service = _build_deps()
    app = build_test_app(deps)
    first = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        headers={"Idempotency-Key": "upload-key-2"},
        json={
            "filename": "sample.csv",
            "size_bytes": 42,
            "content_type": "text/csv",
        },
    )
    second = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        headers={"Idempotency-Key": "upload-key-2"},
        json={
            "filename": "sample.csv",
            "size_bytes": 84,
            "content_type": "text/csv",
        },
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"
    assert transfer_service.calls == 1


@pytest.mark.asyncio
async def test_v1_jobs_allows_missing_idempotency_key_when_enabled() -> None:
    """Verify `/v1/jobs` accepts requests without Idempotency-Key."""
    deps, _transfer_service, job_service = _build_deps()
    app = build_test_app(deps)
    response = await request_app(
        app,
        "POST",
        "/v1/jobs",
        json={"job_type": "transform", "payload": {"input": "a"}},
    )
    assert response.status_code == 200
    assert job_service.calls == 1


@pytest.mark.asyncio
async def test_v1_jobs_replays_response_for_same_idempotency_key() -> None:
    """Verify identical key+payload replays the cached enqueue response."""
    deps, _transfer_service, job_service = _build_deps()
    app = build_test_app(deps)
    first = await request_app(
        app,
        "POST",
        "/v1/jobs",
        headers={"Idempotency-Key": "job-key-1"},
        json={"job_type": "transform", "payload": {"input": "a"}},
    )
    second = await request_app(
        app,
        "POST",
        "/v1/jobs",
        headers={"Idempotency-Key": "job-key-1"},
        json={"job_type": "transform", "payload": {"input": "a"}},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    parsed_first = EnqueueJobResponse.model_validate(first.json())
    parsed_second = EnqueueJobResponse.model_validate(second.json())
    assert parsed_first == parsed_second
    assert job_service.calls == 1


@pytest.mark.asyncio
async def test_v1_jobs_reject_key_reuse_with_different_payload() -> None:
    """Verify same key with different payload returns idempotency conflict."""
    deps, _transfer_service, job_service = _build_deps()
    app = build_test_app(deps)
    first = await request_app(
        app,
        "POST",
        "/v1/jobs",
        headers={"Idempotency-Key": "job-key-2"},
        json={"job_type": "transform", "payload": {"input": "a"}},
    )
    second = await request_app(
        app,
        "POST",
        "/v1/jobs",
        headers={"Idempotency-Key": "job-key-2"},
        json={"job_type": "transform", "payload": {"input": "b"}},
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"
    assert job_service.calls == 1


@pytest.mark.asyncio
async def test_v1_jobs_failed_enqueue_is_not_idempotency_replayed() -> None:
    """A failed enqueue must not be replay-cached by idempotency middleware."""
    deps, _transfer_service, _job_service = _build_deps()
    flaky_job_service = _FailFirstEnqueueJobService()
    deps.job_service = flaky_job_service
    app = build_test_app(deps)

    first = await request_app(
        app,
        "POST",
        "/v1/jobs",
        headers={"Idempotency-Key": "job-key-failed-enqueue"},
        json={"job_type": "transform", "payload": {"input": "a"}},
    )
    second = await request_app(
        app,
        "POST",
        "/v1/jobs",
        headers={"Idempotency-Key": "job-key-failed-enqueue"},
        json={"job_type": "transform", "payload": {"input": "a"}},
    )

    assert first.status_code == 503
    assert first.json()["error"]["code"] == "queue_unavailable"
    assert second.status_code == 200
    parsed = EnqueueJobResponse.model_validate(second.json())
    assert parsed.job_id == "job-2"
    assert flaky_job_service.calls == 2


@pytest.mark.asyncio
async def test_v1_initiate_fails_closed_shared_claim_store_unavailable() -> (
    None
):
    """Redis claim-store outages must fail closed before executing work."""
    deps, transfer_service, _job_service = _build_deps()
    failing_shared_cache = _shared_cache_with_client(_ErrorRedisClient())
    _replace_shared_cache(
        deps=deps,
        shared_cache=failing_shared_cache,
    )
    app = build_test_app(deps)

    response = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        headers={"Idempotency-Key": "upload-key-error"},
        json={
            "filename": "sample.csv",
            "size_bytes": 42,
            "content_type": "text/csv",
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "idempotency_unavailable"
    assert transfer_service.calls == 0


@pytest.mark.asyncio
async def test_v1_initiate_store_failure_is_not_replayed() -> None:
    """Commit-store outages must block duplicate execution."""
    deps, transfer_service, _job_service = _build_deps()
    flaky_shared_cache = _shared_cache_with_client(_ClaimOnlyRedisClient())
    _replace_shared_cache(
        deps=deps,
        shared_cache=flaky_shared_cache,
    )
    app = build_test_app(deps)

    first = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        headers={"Idempotency-Key": "upload-key-commit-outage"},
        json={
            "filename": "sample.csv",
            "size_bytes": 42,
            "content_type": "text/csv",
        },
    )
    second = await request_app(
        app,
        "POST",
        "/v1/transfers/uploads/initiate",
        headers={"Idempotency-Key": "upload-key-commit-outage"},
        json={
            "filename": "sample.csv",
            "size_bytes": 42,
            "content_type": "text/csv",
        },
    )

    assert first.status_code == 503
    assert first.json()["error"]["code"] == "idempotency_unavailable"
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"
    assert transfer_service.calls == 1


@pytest.mark.asyncio
async def test_v1_jobs_store_failure_blocks_duplicate_enqueue() -> None:
    """Commit-store outages must not re-run a successful enqueue."""
    deps, _transfer_service, job_service = _build_deps()
    flaky_shared_cache = _shared_cache_with_client(_ClaimOnlyRedisClient())
    _replace_shared_cache(
        deps=deps,
        shared_cache=flaky_shared_cache,
    )
    app = build_test_app(deps)

    first = await request_app(
        app,
        "POST",
        "/v1/jobs",
        headers={"Idempotency-Key": "job-key-commit-outage"},
        json={"job_type": "transform", "payload": {"input": "a"}},
    )
    second = await request_app(
        app,
        "POST",
        "/v1/jobs",
        headers={"Idempotency-Key": "job-key-commit-outage"},
        json={"job_type": "transform", "payload": {"input": "a"}},
    )

    assert first.status_code == 503
    assert first.json()["error"]["code"] == "idempotency_unavailable"
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"
    assert job_service.calls == 1


@pytest.mark.asyncio
async def test_shared_idempotency_store_prevents_duplicate_claims() -> None:
    """Separate store instances sharing Redis must not both claim one key."""
    shared_cache = _shared_cache_with_client(_DictRedisClient())
    first_store = IdempotencyStore(
        shared_cache=shared_cache,
        enabled=True,
        ttl_seconds=300,
        key_prefix="nova",
        key_schema_version=1,
    )
    second_store = IdempotencyStore(
        shared_cache=shared_cache,
        enabled=True,
        ttl_seconds=300,
        key_prefix="nova",
        key_schema_version=1,
    )

    first_claim = await first_store.claim_request(
        route="/v1/jobs",
        scope_id="scope-1",
        idempotency_key="job-key-shared",
        request_payload={"job_type": "transform", "payload": {"input": "a"}},
    )

    assert first_claim is True
    with pytest.raises(Exception, match="already in progress"):
        _ = await second_store.claim_request(
            route="/v1/jobs",
            scope_id="scope-1",
            idempotency_key="job-key-shared",
            request_payload={
                "job_type": "transform",
                "payload": {"input": "a"},
            },
        )


@pytest.mark.asyncio
async def test_claim_request_conflicts_when_claim_entry_expires_before_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expired claim entries must fail closed instead of replaying."""
    store = IdempotencyStore(
        shared_cache=_shared_cache_with_client(_DictRedisClient()),
        enabled=True,
        ttl_seconds=300,
        key_prefix="nova",
        key_schema_version=1,
    )
    write_entry_if_absent = AsyncMock(return_value=False)
    read_entry = AsyncMock(return_value=None)
    assert_request_hash = Mock()

    monkeypatch.setattr(
        store,
        "_write_entry_if_absent",
        write_entry_if_absent,
    )
    monkeypatch.setattr(store, "_read_entry", read_entry)
    monkeypatch.setattr(
        idempotency_module,
        "_assert_entry_request_hash",
        assert_request_hash,
    )

    with pytest.raises(Exception, match="stored idempotency record is invalid"):
        _ = await store.claim_request(
            route="/v1/jobs",
            scope_id="scope-1",
            idempotency_key="job-key-expired-claim",
            request_payload={
                "job_type": "transform",
                "payload": {"input": "a"},
            },
        )

    assert_request_hash.assert_not_called()


@pytest.mark.asyncio
async def test_discard_claim_keeps_newer_owner_when_claim_was_replaced() -> (
    None
):
    """Failure cleanup must not delete a newer claimant's in-progress entry."""
    client = _DictRedisClient()
    shared_cache = _shared_cache_with_client(client)
    store = IdempotencyStore(
        shared_cache=shared_cache,
        enabled=True,
        ttl_seconds=300,
        key_prefix="nova",
        key_schema_version=1,
    )
    first_payload = {"job_type": "transform", "payload": {"input": "a"}}
    second_payload = {"job_type": "transform", "payload": {"input": "b"}}

    claimed = await store.claim_request(
        route="/v1/jobs",
        scope_id="scope-1",
        idempotency_key="job-key-replaced-claim",
        request_payload=first_payload,
    )
    assert claimed is True

    cache_key = namespaced_cache_key(
        namespace="idempotency",
        raw="/v1/jobs|scope-1|job-key-replaced-claim",
        key_prefix="nova",
        key_schema_version=1,
    )
    client.replace_string(
        cache_key,
        json.dumps(
            {
                "state": "in_progress",
                "request_hash": idempotency_request_payload_hash(
                    payload=second_payload,
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    )

    await store.discard_claim(
        route="/v1/jobs",
        scope_id="scope-1",
        idempotency_key="job-key-replaced-claim",
        request_payload=first_payload,
    )

    raw_entry = await client.get(cache_key)
    assert raw_entry is not None
    assert json.loads(raw_entry) == {
        "state": "in_progress",
        "request_hash": idempotency_request_payload_hash(
            payload=second_payload,
        ),
    }
