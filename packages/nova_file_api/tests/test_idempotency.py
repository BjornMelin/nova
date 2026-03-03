from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_app
from nova_file_api.cache import (
    LocalTTLCache,
    SharedRedisCache,
    TwoTierCache,
)
from nova_file_api.config import Settings
from nova_file_api.container import AppContainer
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.jobs import MemoryJobRepository
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import (
    EnqueueJobResponse,
    JobRecord,
    JobStatus,
    Principal,
)
from starlette.requests import Request

from ._test_doubles import StubTransferService


class _StubAuthenticator:
    async def authenticate(
        self,
        *,
        request: Request,
        session_id: str | None,
    ) -> Principal:
        del request, session_id
        return Principal(
            subject="user-1",
            scope_id="scope-1",
            tenant_id=None,
            scopes=(),
            permissions=("metrics:read",),
        )


class _StubJobService:
    def __init__(self) -> None:
        self.calls = 0

    def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
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

    def get(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise RuntimeError("not used by this test")

    def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        del job_id, scope_id
        raise RuntimeError("not used by this test")


def _build_container(
    *,
    idempotency_enabled: bool = True,
) -> tuple[AppContainer, _StubJobService]:
    settings = Settings()
    settings.idempotency_enabled = idempotency_enabled
    settings.jobs_enabled = True
    metrics = MetricsCollector(namespace="Tests")
    shared = SharedRedisCache(url=None)
    cache = TwoTierCache(
        local=LocalTTLCache(ttl_seconds=60, max_entries=128),
        shared=shared,
        shared_ttl_seconds=60,
    )
    job_service = _StubJobService()
    repo = MemoryJobRepository()
    container = AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=_StubAuthenticator(),  # type: ignore[arg-type]
        transfer_service=StubTransferService(),  # type: ignore[arg-type]
        job_repository=repo,
        job_service=job_service,  # type: ignore[arg-type]
        activity_store=MemoryActivityStore(),
        idempotency_store=IdempotencyStore(
            cache=cache,
            enabled=idempotency_enabled,
            ttl_seconds=300,
        ),
    )
    return container, job_service


def test_v1_jobs_allows_missing_idempotency_key_when_enabled() -> None:
    container, job_service = _build_container()
    app = create_app(container_override=container)
    with TestClient(app) as client:
        response = client.post(
            "/v1/jobs",
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
    assert response.status_code == 200
    assert job_service.calls == 1


def test_v1_jobs_replays_response_for_same_idempotency_key() -> None:
    container, job_service = _build_container()
    app = create_app(container_override=container)
    with TestClient(app) as client:
        first = client.post(
            "/v1/jobs",
            headers={"Idempotency-Key": "job-key-1"},
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
        second = client.post(
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


def test_v1_jobs_reject_key_reuse_with_different_payload() -> None:
    container, job_service = _build_container()
    app = create_app(container_override=container)
    with TestClient(app) as client:
        first = client.post(
            "/v1/jobs",
            headers={"Idempotency-Key": "job-key-2"},
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
        second = client.post(
            "/v1/jobs",
            headers={"Idempotency-Key": "job-key-2"},
            json={"job_type": "transform", "payload": {"input": "b"}},
        )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"
    assert job_service.calls == 1
