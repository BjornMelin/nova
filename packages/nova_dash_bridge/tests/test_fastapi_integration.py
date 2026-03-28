"""FastAPI integration tests for the Dash bridge adapter."""

from __future__ import annotations

from typing import Any, cast

import nova_dash_bridge.fastapi_integration as fastapi_integration
import pytest
from fastapi.testclient import TestClient
from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_dash_bridge.s3_client import (
    SupportsCreateAsyncS3Client,
    SupportsCreateS3Client,
)
from nova_dash_bridge.service import AsyncFileTransferService
from nova_file_api.public import (
    TRANSFER_ROUTE_PREFIX,
    UPLOADS_INITIATE_ROUTE,
    InitiateUploadRequest,
    InitiateUploadResponse,
    Principal,
    UploadStrategy,
)


def _auth_policy() -> AuthPolicy:
    async def _resolve_principal_async(
        _authorization_header: str | None,
    ) -> Principal:
        return Principal(subject="user-1", scope_id="scope-1")

    return AuthPolicy(
        principal_resolver=lambda _: Principal(
            subject="user-1",
            scope_id="scope-1",
        ),
        async_principal_resolver=_resolve_principal_async,
    )


def _sync_only_auth_policy() -> AuthPolicy:
    return AuthPolicy(
        principal_resolver=lambda _: Principal(
            subject="user-1",
            scope_id="scope-1",
        ),
    )


class _SyncOnlyS3Factory:
    def create(self, _env: FileTransferEnvConfig) -> object:
        del _env
        return cast(Any, object())


def _env_config() -> FileTransferEnvConfig:
    """Return a fixed file-transfer environment for test isolation."""
    return FileTransferEnvConfig.model_validate(
        {
            "FILE_TRANSFER_ENABLED": True,
            "FILE_TRANSFER_BUCKET": "bucket-a",
        }
    )


def _upload_policy() -> UploadPolicy:
    """Return a fixed upload policy for test isolation."""
    return UploadPolicy(
        max_upload_bytes=100,
        allowed_extensions={".csv"},
    )


def _create_fastapi_app(
    *,
    auth_policy: AuthPolicy | None = None,
    s3_client_factory: SupportsCreateS3Client | None = None,
    async_s3_client_factory: SupportsCreateAsyncS3Client | None = None,
) -> Any:
    """Create a FastAPI app with test defaults and optional overrides."""
    return fastapi_integration.create_fastapi_app(
        env_config=_env_config(),
        upload_policy=_upload_policy(),
        auth_policy=(_auth_policy() if auth_policy is None else auth_policy),
        s3_client_factory=s3_client_factory,
        async_s3_client_factory=async_s3_client_factory,
    )


def test_create_fastapi_app_requires_auth_policy() -> None:
    app_factory = cast(Any, fastapi_integration.create_fastapi_app)
    with pytest.raises(TypeError, match="auth_policy"):
        app_factory(
            env_config=_env_config(),
            upload_policy=_upload_policy(),
        )


def test_create_fastapi_app_calls_async_service_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, int]] = []

    async def _fake_initiate_upload(
        self: AsyncFileTransferService,
        payload: InitiateUploadRequest,
        *,
        principal: Principal,
    ) -> InitiateUploadResponse:
        calls.append((payload.filename, principal.scope_id, payload.size_bytes))
        return InitiateUploadResponse(
            strategy=UploadStrategy.SINGLE,
            bucket="bucket-a",
            key="uploads/scope-1/report.csv",
            url="https://example.invalid/upload",
            expires_in_seconds=900,
        )

    monkeypatch.setattr(
        AsyncFileTransferService,
        "initiate_upload",
        _fake_initiate_upload,
    )

    app = _create_fastapi_app()

    with TestClient(app) as client:
        response = client.post(
            f"{TRANSFER_ROUTE_PREFIX}{UPLOADS_INITIATE_ROUTE}",
            json={
                "filename": "report.csv",
                "content_type": "text/csv",
                "size_bytes": 1,
            },
            headers={"Authorization": "Bearer token-123"},
        )

    assert response.status_code == 200
    assert calls == [("report.csv", "scope-1", 1)]


def test_create_fastapi_app_requires_async_auth_policy() -> None:
    """Reject sync-only auth policies for async FastAPI bridge wiring."""
    with pytest.raises(
        TypeError,
        match=r"auth_policy\.async_principal_resolver",
    ):
        fastapi_integration.create_fastapi_app(
            env_config=_env_config(),
            upload_policy=_upload_policy(),
            auth_policy=_sync_only_auth_policy(),
        )


def test_create_fastapi_app_requires_async_s3_factory() -> None:
    with pytest.raises(
        TypeError,
        match=r"requires async_s3_client_factory or s3_client_factory with "
        r"create_async",
    ):
        fastapi_integration.create_fastapi_app(
            env_config=_env_config(),
            upload_policy=_upload_policy(),
            auth_policy=_auth_policy(),
            s3_client_factory=cast(
                "SupportsCreateS3Client",
                _SyncOnlyS3Factory(),
            ),
        )


def test_create_fastapi_app_uses_async_auth_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth_headers: list[str] = []

    async def _resolve_principal_async(
        authorization_header: str | None,
    ) -> Principal:
        auth_headers.append(authorization_header or "")
        return Principal(subject="user-1", scope_id="scope-1")

    async def _fake_initiate_upload(
        self: AsyncFileTransferService,
        payload: InitiateUploadRequest,
        *,
        principal: Principal,
    ) -> InitiateUploadResponse:
        del self, payload, principal
        return InitiateUploadResponse(
            strategy=UploadStrategy.SINGLE,
            bucket="bucket-a",
            key="uploads/scope-1/report.csv",
            url="https://example.invalid/upload",
            expires_in_seconds=900,
        )

    monkeypatch.setattr(
        AsyncFileTransferService,
        "initiate_upload",
        _fake_initiate_upload,
    )

    app = _create_fastapi_app(
        auth_policy=AuthPolicy(
            async_principal_resolver=_resolve_principal_async
        )
    )

    with TestClient(app) as client:
        response = client.post(
            f"{TRANSFER_ROUTE_PREFIX}{UPLOADS_INITIATE_ROUTE}",
            json={
                "filename": "report.csv",
                "content_type": "text/csv",
                "size_bytes": 1,
            },
            headers={"Authorization": "Bearer token-123"},
        )

    assert response.status_code == 200
    assert auth_headers == ["Bearer token-123"]


def test_routes_include_transfer_operation_metadata() -> None:
    """Ensure OpenAPI operation metadata stays stable for transfer endpoints."""

    app = _create_fastapi_app()
    with TestClient(app) as client:
        openapi_doc = client.get("/openapi.json").json()

    operation = openapi_doc["paths"]["/v1/transfers/uploads/initiate"]["post"]
    assert operation["operationId"] == "initiate_upload"
    assert operation["tags"] == ["transfers"]
    assert operation["security"] == [{"bearerAuth": []}]
    assert (
        openapi_doc["components"]["securitySchemes"]["bearerAuth"]["scheme"]
        == "bearer"
    )


@pytest.mark.parametrize(
    ("body", "headers"),
    [
        ("{}", {"Content-Type": "application/json"}),
        ('{"filename":', {"Content-Type": "application/json"}),
    ],
)
def test_create_fastapi_app_wraps_request_validation_errors(
    body: str,
    headers: dict[str, str],
) -> None:
    """Ensure malformed bodies are wrapped in canonical error envelopes."""

    app = _create_fastapi_app()
    with TestClient(app) as client:
        response = client.post(
            f"{TRANSFER_ROUTE_PREFIX}{UPLOADS_INITIATE_ROUTE}",
            content=body,
            headers={
                **headers,
                "Authorization": "Bearer token-123",
                "X-Request-Id": "req-bridge-422",
            },
        )

    assert response.status_code == 422
    assert response.headers["X-Request-Id"] == "req-bridge-422"
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["message"] == "request validation failed"
    assert payload["error"]["request_id"] == "req-bridge-422"
    assert payload["error"]["details"]


def test_create_fastapi_app_requires_bearer_auth() -> None:
    """Ensure missing credentials are rejected before request validation."""

    app = _create_fastapi_app()
    with TestClient(app) as client:
        response = client.post(
            f"{TRANSFER_ROUTE_PREFIX}{UPLOADS_INITIATE_ROUTE}",
            content="{}",
            headers={
                "Content-Type": "application/json",
                "X-Request-Id": "req-bridge-401",
            },
        )

    assert response.status_code == 401
    assert response.headers["X-Request-Id"] == "req-bridge-401"
    payload = response.json()
    assert payload["error"]["code"] == "unauthorized"
    assert payload["error"]["message"] == "missing bearer token"
    assert payload["error"]["request_id"] == "req-bridge-401"
    assert response.headers["WWW-Authenticate"].startswith("Bearer")


def test_create_fastapi_app_rejects_cookie_only_auth() -> None:
    """Ensure bridge auth does not fall back to ambient browser cookies."""

    app = _create_fastapi_app()
    with TestClient(app) as client:
        client.cookies.set("pca-nova-auth", "Bearer token-123")
        response = client.post(
            f"{TRANSFER_ROUTE_PREFIX}{UPLOADS_INITIATE_ROUTE}",
            content="{}",
            headers={
                "Content-Type": "application/json",
                "X-Request-Id": "req-bridge-cookie-401",
            },
        )

    assert response.status_code == 401
    assert response.headers["X-Request-Id"] == "req-bridge-cookie-401"
    payload = response.json()
    assert payload["error"]["code"] == "unauthorized"
    assert payload["error"]["message"] == "missing bearer token"
    assert payload["error"]["request_id"] == "req-bridge-cookie-401"


def test_fastapi_app_generates_request_id_for_validation_errors() -> None:
    """Validation failures should mint and return a request ID when absent."""

    app = _create_fastapi_app()
    with TestClient(app) as client:
        response = client.post(
            f"{TRANSFER_ROUTE_PREFIX}{UPLOADS_INITIATE_ROUTE}",
            content="{}",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer token-123",
            },
        )

    assert response.status_code == 422
    request_id = response.headers["X-Request-Id"]
    assert request_id
    assert response.json()["error"]["request_id"] == request_id


def test_create_fastapi_app_wraps_unhandled_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected bridge failures should return canonical 500 responses."""

    async def _boom(
        self: AsyncFileTransferService,
        payload: InitiateUploadRequest,
        *,
        principal: Principal,
    ) -> InitiateUploadResponse:
        del self, payload, principal
        raise RuntimeError("boom")

    monkeypatch.setattr(
        AsyncFileTransferService,
        "initiate_upload",
        _boom,
    )
    app = _create_fastapi_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"{TRANSFER_ROUTE_PREFIX}{UPLOADS_INITIATE_ROUTE}",
            json={
                "filename": "report.csv",
                "content_type": "text/csv",
                "size_bytes": 1,
            },
            headers={
                "Authorization": "Bearer token-123",
                "X-Request-Id": "req-bridge-500",
            },
        )

    assert response.status_code == 500
    assert response.headers["X-Request-Id"] == "req-bridge-500"
    payload = response.json()
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["request_id"] == "req-bridge-500"
