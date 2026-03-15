from __future__ import annotations

import nova_dash_bridge.fastapi_integration as fastapi_integration
import pytest
from fastapi.testclient import TestClient
from nova_dash_bridge.config import FileTransferEnvConfig, UploadPolicy
from nova_file_api.public import TRANSFER_ROUTE_PREFIX


def test_create_fastapi_app_uses_lifespan_startup(
    monkeypatch,
) -> None:
    calls: list[int] = []

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
    )

    with TestClient(app) as client:
        assert TRANSFER_ROUTE_PREFIX in client.get("/openapi.json").text

    assert calls == [12]


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
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/transfers/uploads/initiate",
            content=body,
            headers=headers,
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["message"] == "request validation failed"
    assert payload["error"]["details"]
