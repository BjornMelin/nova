"""Native Lambda handler contract tests for the FastAPI runtime."""

from __future__ import annotations

import asyncio
import importlib
import json
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.config import Settings
from nova_file_api.exports import (
    ExportService,
    MemoryExportPublisher,
    MemoryExportRepository,
)
from nova_file_api.lambda_handler import create_lambda_handler
from nova_file_api.metrics import MetricsCollector

from .support.app import build_cache_stack, build_runtime_deps, build_test_app
from .support.doubles import StubAuthenticator, StubTransferService


@contextmanager
def _event_loop() -> Any:
    """Provide a current event loop for Mangum initialization in tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def _build_handler() -> Any:
    settings = Settings.model_validate(
        {
            "jobs_enabled": True,
            "idempotency_dynamodb_table": "test-idempotency",
            "cors_allowed_origins": ["https://app.example.com"],
        }
    )
    metrics = MetricsCollector(namespace="Tests")
    cache = build_cache_stack()
    repository = MemoryExportRepository()
    app = build_test_app(
        build_runtime_deps(
            settings=settings,
            metrics=metrics,
            cache=cache,
            authenticator=StubAuthenticator(),
            transfer_service=StubTransferService(),
            export_service=ExportService(
                repository=repository,
                publisher=MemoryExportPublisher(),
                metrics=metrics,
            ),
            activity_store=MemoryActivityStore(),
            idempotency_enabled=True,
        )
    )
    return create_lambda_handler(app=app)


def _rest_api_event(
    *,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: dict[str, object] | None = None,
) -> dict[str, Any]:
    resolved_headers = {"Host": "api.example.com", **(headers or {})}
    return {
        "resource": "/{proxy+}",
        "path": path,
        "httpMethod": method,
        "headers": resolved_headers,
        "multiValueHeaders": {
            key: [value] for key, value in resolved_headers.items()
        },
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "pathParameters": {"proxy": path.removeprefix("/")},
        "stageVariables": None,
        "requestContext": {
            "accountId": "123456789012",
            "resourceId": "resource-id",
            "stage": "dev",
            "requestId": "request-id",
            "identity": {"sourceIp": "127.0.0.1", "userAgent": "pytest"},
            "resourcePath": "/{proxy+}",
            "httpMethod": method,
            "apiId": "api-id",
        },
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


def _normalized_headers(payload: dict[str, Any]) -> dict[str, str]:
    headers = payload.get("headers") or {}
    return {str(key).lower(): str(value) for key, value in headers.items()}


def test_default_lambda_handler_builds_canonical_app_once() -> None:
    """Module import should build the canonical handler only once."""
    import nova_file_api.lambda_handler as lambda_handler

    importlib.reload(lambda_handler)
    original_default_handler = lambda_handler._DEFAULT_HANDLER
    lambda_handler._DEFAULT_HANDLER = None

    handler_mock = Mock(return_value={"statusCode": 200, "body": ""})
    try:
        with (
            patch.object(
                lambda_handler,
                "create_app",
                return_value=object(),
            ) as create_app,
            patch.object(
                lambda_handler,
                "Mangum",
                return_value=handler_mock,
            ) as mangum,
        ):
            lambda_handler.handler(
                _rest_api_event(method="GET", path="/v1/health/live"),
                {},
            )
            lambda_handler.handler(
                _rest_api_event(method="GET", path="/v1/health/live"),
                {},
            )

            assert create_app.call_count == 1
            mangum.assert_called_once()
            assert handler_mock.call_count == 2
    finally:
        lambda_handler._DEFAULT_HANDLER = original_default_handler


def test_native_lambda_handler_serves_public_release_info() -> None:
    """A REST API proxy event should invoke the FastAPI app successfully."""
    with _event_loop():
        handler = _build_handler()

        response: dict[str, Any] = handler(
            _rest_api_event(
                method="GET",
                path="/v1/releases/info",
                headers={"Origin": "https://app.example.com"},
            ),
            {},
        )

        assert response["statusCode"] == 200
        payload = json.loads(response["body"])
        assert payload["name"]
        assert payload["version"]
        assert payload["environment"]
        assert (
            _normalized_headers(response)["access-control-allow-origin"]
            == "https://app.example.com"
        )


def test_native_lambda_handler_answers_cors_preflight() -> None:
    """The Lambda proxy handler should answer browser preflight requests."""
    with _event_loop():
        handler = _build_handler()

        response: dict[str, Any] = handler(
            _rest_api_event(
                method="OPTIONS",
                path="/v1/exports",
                headers={
                    "Origin": "https://app.example.com",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": (
                        "authorization,content-type,idempotency-key"
                    ),
                },
            ),
            {},
        )

        headers = _normalized_headers(response)
        assert response["statusCode"] == 200
        assert (
            headers["access-control-allow-origin"] == "https://app.example.com"
        )
        assert "POST" in headers["access-control-allow-methods"]
        assert (
            "authorization" in headers["access-control-allow-headers"].lower()
        )
