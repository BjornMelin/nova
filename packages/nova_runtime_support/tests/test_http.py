"""Tests for shared ASGI/FastAPI HTTP helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from nova_runtime_support.http import (
    CanonicalErrorSpec,
    RequestContextASGIMiddleware,
    RequestContextFastAPI,
    register_fastapi_exception_handlers,
)
from starlette.types import Message, Receive, Scope, Send


@dataclass(slots=True)
class DemoError(Exception):
    """Test exception used to exercise shared handler registration."""

    code: str
    message: str
    status_code: int

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


async def _stream_chunks() -> AsyncIterator[bytes]:
    """Yield a tiny streaming body for middleware regression coverage."""
    yield b"alpha"
    yield b"beta"


def _demo_error_spec(exc: DemoError) -> CanonicalErrorSpec:
    """Adapt a test domain error into the shared transport shape."""
    return CanonicalErrorSpec(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
    )


def _validation_error_details(
    exc: RequestValidationError,
) -> dict[str, object]:
    """Return public validation details for the shared handler tests."""
    return {"errors": exc.errors()}


def _internal_error_spec(_: Exception) -> CanonicalErrorSpec:
    """Return a fixed canonical internal-error payload for tests."""
    return CanonicalErrorSpec(
        status_code=500,
        code="internal_error",
        message="unexpected internal error",
    )


def _build_test_app() -> FastAPI:
    """Create a FastAPI app using the shared middleware and handlers."""
    app = RequestContextFastAPI()
    register_fastapi_exception_handlers(
        app,
        domain_error_type=DemoError,
        adapt_domain_error=_demo_error_spec,
        validation_error_details=_validation_error_details,
        adapt_unhandled_error=_internal_error_spec,
        logger_name="tests.runtime_support",
    )

    @app.get("/ok")
    async def ok(request: Request) -> dict[str, str]:
        return {"request_id": request.state.request_id}

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        return StreamingResponse(_stream_chunks(), media_type="text/plain")

    @app.get("/domain-error")
    async def domain_error() -> None:
        raise DemoError(
            code="conflict",
            message="domain failure",
            status_code=409,
        )

    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("boom")

    @app.get("/items/{item_id}")
    async def items(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    return app


@pytest.mark.asyncio
async def test_request_context_middleware_passthroughs_non_http() -> None:
    """Non-HTTP scopes should pass through untouched."""
    messages: list[Scope] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        del receive
        messages.append(scope)
        await send({"type": "websocket.close", "code": 1000})

    middleware = RequestContextASGIMiddleware(app)

    sent: list[Message] = []

    async def receive() -> Message:
        return {"type": "websocket.connect"}

    async def send(message: Message) -> None:
        sent.append(message)

    await middleware({"type": "websocket"}, receive, send)

    assert messages == [{"type": "websocket"}]
    assert sent == [{"type": "websocket.close", "code": 1000}]


def test_shared_middleware_echoes_request_id_on_success() -> None:
    """Success responses should echo the caller request ID."""
    app = _build_test_app()

    with TestClient(app) as client:
        response = client.get("/ok", headers={"X-Request-Id": "req-shared-ok"})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "req-shared-ok"
    assert response.json() == {"request_id": "req-shared-ok"}


def test_shared_middleware_generates_request_id_when_missing() -> None:
    """Success responses should mint and expose a request ID when absent."""
    app = _build_test_app()

    with TestClient(app) as client:
        response = client.get("/ok")

    assert response.status_code == 200
    request_id = response.headers["X-Request-Id"]
    assert request_id
    assert response.json() == {"request_id": request_id}


def test_shared_handlers_attach_request_id_to_domain_errors() -> None:
    """Handled domain errors should preserve request-id parity."""
    app = _build_test_app()

    with TestClient(app) as client:
        response = client.get(
            "/domain-error",
            headers={"X-Request-Id": "req-domain-error"},
        )

    assert response.status_code == 409
    assert response.headers["X-Request-Id"] == "req-domain-error"
    payload = response.json()
    assert payload["error"]["code"] == "conflict"
    assert payload["error"]["request_id"] == "req-domain-error"


def test_shared_handlers_attach_request_id_to_unhandled_errors() -> None:
    """Unhandled errors should still produce canonical body/header parity."""
    app = _build_test_app()

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/crash", headers={"X-Request-Id": "req-crash"})

    assert response.status_code == 500
    assert response.headers["X-Request-Id"] == "req-crash"
    payload = response.json()
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["request_id"] == "req-crash"


def test_shared_handlers_keep_validation_errors_canonical() -> None:
    """Validation errors should use the canonical envelope and header."""
    app = _build_test_app()

    with TestClient(app) as client:
        response = client.get(
            "/items/not-an-int",
            headers={"X-Request-Id": "req-validation"},
        )

    assert response.status_code == 422
    assert response.headers["X-Request-Id"] == "req-validation"
    payload = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["request_id"] == "req-validation"
    assert payload["error"]["details"]["errors"]


def test_shared_middleware_preserves_streaming_responses() -> None:
    """Streaming responses should keep their body and still get the header."""
    app = _build_test_app()

    with TestClient(app) as client:
        response = client.get("/stream")

    assert response.status_code == 200
    assert response.headers["X-Request-Id"]
    assert response.text == "alphabeta"
