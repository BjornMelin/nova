from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from nova_dash_bridge.config import FileTransferEnvConfig, UploadPolicy
from nova_dash_bridge.fastapi_integration import create_fastapi_app
from nova_dash_bridge.models import (
    CompleteUploadResponse,
    InitiateUploadResponseSingle,
)
from nova_dash_bridge.service import FileTransferService


def test_bridge_fastapi_uses_local_blocking_io_limiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {"limiters": []}

    def _fake_initiate_upload(
        self: FileTransferService,
        payload: Any,
    ) -> InitiateUploadResponseSingle:
        calls["payload"] = payload
        del self
        return InitiateUploadResponseSingle(
            bucket="bucket-a",
            key="uploads/scope/file.csv",
            url="https://example.com/upload",
            expires_in_seconds=900,
        )

    async def _run_sync(func: Any, *args: Any, **kwargs: Any) -> Any:
        limiter = kwargs.get("limiter")
        if limiter is not None:
            calls["limiters"].append(limiter.total_tokens)
        return func(*args)

    monkeypatch.setattr(
        FileTransferService,
        "initiate_upload",
        _fake_initiate_upload,
    )
    monkeypatch.setattr(
        "nova_dash_bridge.fastapi_integration.anyio.to_thread.run_sync",
        _run_sync,
    )

    env_config = FileTransferEnvConfig(
        enabled=True,
        bucket="bucket-a",
    )
    env_config.thread_tokens = 7

    app = create_fastapi_app(
        env_config=env_config,
        upload_policy=UploadPolicy(
            max_upload_bytes=1_000_000,
            allowed_extensions={".csv"},
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/transfers/uploads/initiate",
            json={
                "filename": "report.csv",
                "content_type": "text/csv",
                "size_bytes": 32,
                "session_id": "0123456789abcdef",
            },
        )

    assert response.status_code == 200
    assert response.json()["strategy"] == "single"
    assert calls["payload"].session_id == "0123456789abcdef"
    assert 7 in calls["limiters"]


def test_bridge_fastapi_complete_upload_returns_etag_and_version_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {"limiters": []}

    def _fake_complete_upload(
        self: FileTransferService,
        payload: Any,
    ) -> CompleteUploadResponse:
        calls["payload"] = payload
        del self
        return CompleteUploadResponse(
            bucket="bucket-a",
            key="uploads/scope/report.csv",
            etag='"etag-123"',
            version_id="version-123",
        )

    async def _run_sync(func: Any, *args: Any, **kwargs: Any) -> Any:
        limiter = kwargs.get("limiter")
        if limiter is not None:
            calls["limiters"].append(limiter.total_tokens)
        return func(*args)

    monkeypatch.setattr(
        FileTransferService,
        "complete_upload",
        _fake_complete_upload,
    )
    monkeypatch.setattr(
        "nova_dash_bridge.fastapi_integration.anyio.to_thread.run_sync",
        _run_sync,
    )

    env_config = FileTransferEnvConfig(
        enabled=True,
        bucket="bucket-a",
    )
    env_config.thread_tokens = 9

    app = create_fastapi_app(
        env_config=env_config,
        upload_policy=UploadPolicy(
            max_upload_bytes=1_000_000,
            allowed_extensions={".csv"},
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/transfers/uploads/complete",
            json={
                "key": "uploads/scope/report.csv",
                "upload_id": "upload-123",
                "parts": [{"part_number": 1, "etag": '"etag-1"'}],
                "session_id": "0123456789abcdef",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "bucket": "bucket-a",
        "key": "uploads/scope/report.csv",
        "etag": '"etag-123"',
        "version_id": "version-123",
    }
    assert calls["payload"].session_id == "0123456789abcdef"
    assert calls["payload"].parts[0].etag == '"etag-1"'
    assert 9 in calls["limiters"]
