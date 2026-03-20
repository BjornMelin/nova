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
from nova_file_api.public import (
    TRANSFER_ROUTE_PREFIX,
    UPLOADS_INITIATE_ROUTE,
    Principal,
)


def _auth_policy() -> AuthPolicy:
    return AuthPolicy(
        principal_resolver=lambda _: Principal(
            subject="user-1",
            scope_id="scope-1",
        )
    )


def test_create_fastapi_app_requires_auth_policy() -> None:
    app_factory = cast(Any, fastapi_integration.create_fastapi_app)
    with pytest.raises(TypeError, match="auth_policy"):
        app_factory(
            env_config=FileTransferEnvConfig.model_validate(
                {
                    "FILE_TRANSFER_ENABLED": True,
                    "FILE_TRANSFER_BUCKET": "bucket-a",
                }
            ),
            upload_policy=UploadPolicy(
                max_upload_bytes=100,
                allowed_extensions={".csv"},
            ),
        )


def test_create_fastapi_app_uses_lifespan_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify startup configures and shutdown restores thread limiter tokens."""
    calls: list[int] = []
    token_var = 40

    class _DummyLimiter:
        total_tokens = token_var

    monkeypatch.setattr(
        fastapi_integration,
        "current_default_thread_limiter",
        lambda: _DummyLimiter(),
    )
    original_token = token_var
    calls.append(token_var)

    monkeypatch.setattr(
        fastapi_integration,
        "_configure_thread_limiter",
        lambda *, total_tokens: calls.append(total_tokens),
    )

    app = fastapi_integration.create_fastapi_app(
        env_config=FileTransferEnvConfig.model_validate(
            {
                "FILE_TRANSFER_ENABLED": True,
                "FILE_TRANSFER_BUCKET": "bucket-a",
                "FILE_TRANSFER_THREAD_TOKENS": 12,
            }
        ),
        upload_policy=UploadPolicy(
            max_upload_bytes=100,
            allowed_extensions={".csv"},
        ),
        auth_policy=_auth_policy(),
    )

    with TestClient(app) as client:
        assert TRANSFER_ROUTE_PREFIX in client.get("/openapi.json").text

    assert calls == [original_token, 12, original_token]
    token_var = calls[-1]
    assert token_var == original_token


def test_routes_include_transfer_operation_metadata() -> None:
    """Ensure OpenAPI operation metadata stays stable for transfer endpoints."""
    app = fastapi_integration.create_fastapi_app(
        env_config=FileTransferEnvConfig.model_validate(
            {
                "FILE_TRANSFER_ENABLED": True,
                "FILE_TRANSFER_BUCKET": "bucket-a",
            }
        ),
        upload_policy=UploadPolicy(
            max_upload_bytes=100,
            allowed_extensions={".csv"},
        ),
        auth_policy=_auth_policy(),
    )
    with TestClient(app) as client:
        openapi_doc = client.get("/openapi.json").json()

    operation = openapi_doc["paths"]["/v1/transfers/uploads/initiate"]["post"]
    assert operation["operationId"] == "initiate_upload"
    assert operation["tags"] == ["transfers"]


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
    app = fastapi_integration.create_fastapi_app(
        env_config=FileTransferEnvConfig.model_validate(
            {
                "FILE_TRANSFER_ENABLED": True,
                "FILE_TRANSFER_BUCKET": "bucket-a",
                "FILE_TRANSFER_THREAD_TOKENS": 12,
            }
        ),
        upload_policy=UploadPolicy(
            max_upload_bytes=100,
            allowed_extensions={".csv"},
        ),
        auth_policy=_auth_policy(),
    )
    with TestClient(app) as client:
        response = client.post(
            f"{TRANSFER_ROUTE_PREFIX}{UPLOADS_INITIATE_ROUTE}",
            content=body,
            headers=headers,
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["message"] == "request validation failed"
    assert payload["error"]["details"]
