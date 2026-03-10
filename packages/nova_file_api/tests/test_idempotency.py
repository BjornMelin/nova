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
    InitiateUploadResponse,
    JobRecord,
    JobStatus,
    Principal,
    UploadStrategy,
)
from starlette.requests import Request


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
        """
        Create a stub service instance that tracks invocation count.
        
        Initializes an internal counter `calls` to 0 for tests to verify how many times the service's methods are invoked.
        """
        self.calls = 0

    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        scope_id: str,
    ) -> JobRecord:
        """
        Create and return a new pending JobRecord with a generated job_id and timestamps set to the current UTC time.
        
        Parameters:
            job_type (str): Logical type or name of the job.
            payload (dict[str, Any]): Payload provided to the job.
            scope_id (str): Identifier of the scope the job belongs to.
        
        Returns:
            JobRecord: The enqueued job record with status `JobStatus.PENDING`, a generated `job_id` of the form `"job-{n}"`, and `created_at`/`updated_at` set to the current UTC time.
        """
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
        """
        Indicates the stubbed get method is not used by tests by always raising a RuntimeError.
        
        Raises:
            RuntimeError: Always raised with message "not used by this test".
        """
        del job_id, scope_id
        raise RuntimeError("not used by this test")

    async def cancel(self, *, job_id: str, scope_id: str) -> JobRecord:
        """
        This stub method is intentionally unusable in tests and always raises a RuntimeError.
        
        Raises:
            RuntimeError: Always raised with message "not used by this test".
        """
        del job_id, scope_id
        raise RuntimeError("not used by this test")


class _StubTransferService:
    def __init__(self) -> None:
        """
        Create a stub service instance that tracks invocation count.
        
        Initializes an internal counter `calls` to 0 for tests to verify how many times the service's methods are invoked.
        """
        self.calls = 0

    async def initiate_upload(
        self,
        payload: Any,
        principal: Principal,
    ) -> InitiateUploadResponse:
        """
        Produce a deterministic InitiateUploadResponse for tests using the single-part upload strategy.
        
        This stub ignores its inputs and increments an internal call counter; the counter value is embedded in the returned key and url.
        
        Parameters:
            payload (Any): Ignored by this stub.
            principal (Principal): Ignored by this stub.
        
        Returns:
            InitiateUploadResponse: Response with
                - strategy: UploadStrategy.SINGLE
                - bucket: "bucket-a"
                - key: "uploads/scope-1/object-{n}" where {n} is the internal call index
                - expires_in_seconds: 900
                - url: "https://example.local/upload/{n}" where {n} is the internal call index
        """
        del payload, principal
        self.calls += 1
        return InitiateUploadResponse(
            strategy=UploadStrategy.SINGLE,
            bucket="bucket-a",
            key=f"uploads/scope-1/object-{self.calls}",
            expires_in_seconds=900,
            url=f"https://example.local/upload/{self.calls}",
        )


def _build_container(
    *,
    idempotency_enabled: bool = True,
) -> tuple[AppContainer, _StubTransferService, _StubJobService]:
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
    transfer_service = _StubTransferService()
    job_service = _StubJobService()
    repo = MemoryJobRepository()
    container = AppContainer(
        settings=settings,
        metrics=metrics,
        cache=cache,
        shared_cache=shared,
        authenticator=_StubAuthenticator(),  # type: ignore[arg-type]
        transfer_service=transfer_service,  # type: ignore[arg-type]
        job_repository=repo,
        job_service=job_service,  # type: ignore[arg-type]
        activity_store=MemoryActivityStore(),
        idempotency_store=IdempotencyStore(
            cache=cache,
            enabled=idempotency_enabled,
            ttl_seconds=300,
        ),
    )
    return container, transfer_service, job_service


def test_v1_initiate_allows_missing_idempotency_key_when_enabled() -> None:
    """Verify `/v1/transfers/uploads/initiate` accepts requests without key."""
    container, transfer_service, _job_service = _build_container()
    app = create_app(container_override=container)
    with TestClient(app) as client:
        response = client.post(
            "/v1/transfers/uploads/initiate",
            json={
                "filename": "sample.csv",
                "size_bytes": 42,
                "content_type": "text/csv",
            },
        )
    assert response.status_code == 200
    assert transfer_service.calls == 1


def test_v1_initiate_replays_response_for_same_idempotency_key() -> None:
    """Verify same initiate key+payload replays the cached response."""
    container, transfer_service, _job_service = _build_container()
    app = create_app(container_override=container)
    with TestClient(app) as client:
        first = client.post(
            "/v1/transfers/uploads/initiate",
            headers={"Idempotency-Key": "upload-key-1"},
            json={
                "filename": "sample.csv",
                "size_bytes": 42,
                "content_type": "text/csv",
            },
        )
        second = client.post(
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


def test_v1_initiate_rejects_key_reuse_with_different_payload() -> None:
    """Verify key reuse with different initiate payload returns conflict."""
    container, transfer_service, _job_service = _build_container()
    app = create_app(container_override=container)
    with TestClient(app) as client:
        first = client.post(
            "/v1/transfers/uploads/initiate",
            headers={"Idempotency-Key": "upload-key-2"},
            json={
                "filename": "sample.csv",
                "size_bytes": 42,
                "content_type": "text/csv",
            },
        )
        second = client.post(
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


def test_v1_jobs_allows_missing_idempotency_key_when_enabled() -> None:
    """Verify `/v1/jobs` accepts requests without Idempotency-Key."""
    container, _transfer_service, job_service = _build_container()
    app = create_app(container_override=container)
    with TestClient(app) as client:
        response = client.post(
            "/v1/jobs",
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
    assert response.status_code == 200
    assert job_service.calls == 1


def test_v1_jobs_replays_response_for_same_idempotency_key() -> None:
    """Verify identical key+payload replays the cached enqueue response."""
    container, _transfer_service, job_service = _build_container()
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
    """Verify same key with different payload returns idempotency conflict."""
    container, _transfer_service, job_service = _build_container()
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