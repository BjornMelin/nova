"""Native Lambda handler contract tests for the FastAPI runtime."""

from __future__ import annotations

import asyncio
import importlib
import json
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, patch

import pytest
from mangum import Mangum

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.app import create_app, create_managed_app
from nova_file_api.config import Settings
from nova_file_api.exports import (
    ExportService,
    MemoryExportPublisher,
    MemoryExportRepository,
)
from nova_file_api.runtime import RuntimeBootstrap
from nova_runtime_support.metrics import MetricsCollector

from .support.app import (
    build_cache_stack,
    build_runtime_deps,
    build_test_app,
    build_test_runtime,
)
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
            "exports_enabled": True,
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
    return Mangum(app, lifespan="auto")


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


def test_default_lambda_handler_bootstraps_runtime_once() -> None:
    """Module import should bootstrap the canonical runtime only once."""
    import nova_file_api.lambda_handler as lambda_handler

    importlib.reload(lambda_handler)
    original_default_handler = lambda_handler._DEFAULT_HANDLER
    original_runtime_bootstrap = lambda_handler._DEFAULT_RUNTIME_BOOTSTRAP
    original_bootstrap_loop = lambda_handler._DEFAULT_BOOTSTRAP_LOOP
    lambda_handler._DEFAULT_HANDLER = None
    lambda_handler._DEFAULT_RUNTIME_BOOTSTRAP = None
    lambda_handler._DEFAULT_BOOTSTRAP_LOOP = None

    handler_mock = Mock(return_value={"statusCode": 200, "body": ""})
    bootstrap = RuntimeBootstrap(runtime=cast(Any, SimpleNamespace()))
    try:
        with (
            patch.object(
                lambda_handler,
                "bootstrap_api_runtime",
                autospec=True,
            ) as bootstrap_api_runtime,
            patch.object(
                lambda_handler,
                "Settings",
                return_value=Settings.model_validate(
                    {"IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency"}
                ),
            ),
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
            bootstrap_api_runtime.return_value = bootstrap
            lambda_handler.handler(
                _rest_api_event(method="GET", path="/v1/health/live"),
                {},
            )
            lambda_handler.handler(
                _rest_api_event(method="GET", path="/v1/health/live"),
                {},
            )

            assert bootstrap_api_runtime.call_count == 1
            assert create_app.call_count == 1
            mangum.assert_called_once()
            assert mangum.call_args.kwargs["lifespan"] == "off"
            assert handler_mock.call_count == 2
    finally:
        created_bootstrap_loop = lambda_handler._DEFAULT_BOOTSTRAP_LOOP
        if (
            created_bootstrap_loop is not None
            and created_bootstrap_loop is not original_bootstrap_loop
            and not created_bootstrap_loop.is_closed()
        ):
            created_bootstrap_loop.close()
        lambda_handler._DEFAULT_HANDLER = original_default_handler
        lambda_handler._DEFAULT_RUNTIME_BOOTSTRAP = original_runtime_bootstrap
        lambda_handler._DEFAULT_BOOTSTRAP_LOOP = original_bootstrap_loop


def test_create_app_requires_prebuilt_runtime() -> None:
    """The pure app builder should require one prebuilt runtime container."""
    with pytest.raises(TypeError):
        cast(Any, create_app)()


def test_managed_app_via_mangum_auto_bootstraps_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caller-managed apps should use Mangum lifespan to install runtime."""
    import nova_file_api.app as app_module

    bootstrap_calls = 0
    settings = Settings.model_validate(
        {
            "exports_enabled": True,
            "idempotency_dynamodb_table": "test-idempotency",
            "cors_allowed_origins": ["https://app.example.com"],
        }
    )

    async def _fake_bootstrap_api_runtime(
        *,
        settings: Settings,
    ) -> RuntimeBootstrap:
        nonlocal bootstrap_calls
        bootstrap_calls += 1
        metrics = MetricsCollector(namespace="Tests")
        repository = MemoryExportRepository()
        return RuntimeBootstrap(
            runtime=build_test_runtime(
                build_runtime_deps(
                    settings=settings,
                    metrics=metrics,
                    cache=build_cache_stack(),
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
        )

    monkeypatch.setattr(
        app_module,
        "bootstrap_api_runtime",
        _fake_bootstrap_api_runtime,
    )

    with _event_loop():
        handler = Mangum(
            create_managed_app(settings=settings),
            lifespan="auto",
        )

        response: dict[str, Any] = handler(
            _rest_api_event(
                method="GET",
                path="/v1/releases/info",
                headers={"Origin": "https://app.example.com"},
            ),
            cast(Any, SimpleNamespace()),
        )

    assert bootstrap_calls == 1
    assert response["statusCode"] == 200


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
