from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from nova_auth_api.app import create_app
from nova_auth_api.config import Settings
from nova_auth_api.errors import unauthorized
from nova_auth_api.models import (
    Principal,
    TokenIntrospectRequest,
    TokenIntrospectResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
)
from nova_auth_api.service import TokenVerificationService


class _StubService(TokenVerificationService):
    def __init__(self) -> None:  # pragma: no cover - test stub init
        super().__init__(settings=Settings())

    async def verify(self, request: TokenVerifyRequest) -> TokenVerifyResponse:
        if request.access_token == "invalid":
            raise unauthorized("invalid token")
        return TokenVerifyResponse(
            principal=Principal(subject="sub", scope_id="scope"),
            claims={"sub": "sub"},
        )

    async def introspect(
        self,
        request: TokenIntrospectRequest,
    ) -> TokenIntrospectResponse:
        if request.access_token == "invalid":
            raise unauthorized("invalid token")
        return TokenIntrospectResponse(
            active=True,
            principal=Principal(subject="sub", scope_id="scope"),
            claims={"sub": "sub"},
        )

    def is_ready(self) -> bool:
        return True


class _NotReadyStubService(_StubService):
    def is_ready(self) -> bool:
        return False


def test_v1_health_live() -> None:
    """Verify liveness endpoint returns an OK payload and request id."""
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.get("/v1/health/live")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "nova-auth-api"
    assert isinstance(payload["request_id"], str)
    assert payload["request_id"]


def test_v1_health_ready() -> None:
    """Verify readiness endpoint returns an OK payload when service is ready."""
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.get("/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "nova-auth-api"
    assert isinstance(payload["request_id"], str)
    assert payload["request_id"]


def test_v1_health_ready_returns_503_when_verifier_missing() -> None:
    """Verify readiness endpoint returns 503 when verifier is unavailable."""
    app = create_app(service_override=_NotReadyStubService())
    with TestClient(app) as client:
        response = client.get(
            "/v1/health/ready",
            headers={"X-Request-Id": "req-auth-ready-503"},
        )
    assert response.status_code == 503
    payload: dict[str, Any] = response.json()
    assert payload["error"]["code"] == "service_unavailable"
    assert payload["error"]["message"] == "auth verifier unavailable"
    assert payload["error"]["request_id"] == "req-auth-ready-503"


def test_verify_endpoint() -> None:
    """Verify token endpoint returns principal and claims on success."""
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.post(
            "/v1/token/verify",
            json={"access_token": "ok"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["principal"]["subject"] == "sub"
    assert payload["claims"]["sub"] == "sub"


def test_error_envelope_for_unauthorized_token() -> None:
    """Verify unauthorized introspection returns canonical error envelope."""
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.post(
            "/v1/token/introspect",
            headers={"X-Request-Id": "req-1"},
            json={"access_token": "invalid"},
        )
    assert response.status_code == 401
    payload: dict[str, Any] = response.json()
    assert payload["error"]["code"] == "unauthorized"
    assert payload["error"]["request_id"] == "req-1"


def test_introspect_success_response_shape() -> None:
    """Verify introspection success payload shape and expected fields."""
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.post(
            "/v1/token/introspect",
            json={"access_token": "ok"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["active"] is True
    assert payload["principal"]["subject"] == "sub"
    assert payload["claims"]["sub"] == "sub"


def test_introspect_accepts_rfc7662_form_payload() -> None:
    """Verify RFC7662 form-encoded introspection payloads are accepted."""
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.post(
            "/v1/token/introspect",
            data={
                "token": "ok",
                "token_type_hint": "access_token",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["active"] is True
    assert payload["principal"]["subject"] == "sub"


def test_introspect_form_payload_requires_token() -> None:
    """Verify missing form token yields canonical validation error response."""
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.post(
            "/v1/token/introspect",
            headers={"X-Request-Id": "req-introspect-422"},
            data={"token_type_hint": "access_token"},
        )
    assert response.status_code == 422
    payload: dict[str, Any] = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["request_id"] == "req-introspect-422"
    assert payload["error"]["details"]["errors"]


def test_introspect_invalid_utf8_json_returns_validation_error() -> None:
    """Verify invalid UTF-8 JSON payloads produce validation errors."""
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.post(
            "/v1/token/introspect",
            headers={
                "content-type": "application/json",
                "X-Request-Id": "req-introspect-invalid-utf8",
            },
            content=b"\xff",
        )
    assert response.status_code == 422
    payload: dict[str, Any] = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["request_id"] == "req-introspect-invalid-utf8"
    assert payload["error"]["details"]["errors"]


def test_verify_validation_error_uses_canonical_error_envelope() -> None:
    """Verify verify endpoint validation failures use canonical envelope."""
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.post(
            "/v1/token/verify",
            headers={"X-Request-Id": "req-verify-422"},
            json={"required_scopes": ["scope:read"]},
        )
    assert response.status_code == 422
    payload: dict[str, Any] = response.json()
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["request_id"] == "req-verify-422"
    assert payload["error"]["details"]["errors"]


def test_verify_validation_error_redacts_access_token_input() -> None:
    """Verify verify endpoint redacts access_token validation inputs."""
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.post(
            "/v1/token/verify",
            headers={"X-Request-Id": "req-verify-redact"},
            json={"access_token": ["secret-token"]},
        )
    assert response.status_code == 422
    payload: dict[str, Any] = response.json()
    errors = payload["error"]["details"]["errors"]
    assert errors
    for error in errors:
        loc = error.get("loc", ())
        if isinstance(loc, (list, tuple)) and "access_token" in loc:
            assert error.get("input") == "[REDACTED]"


def test_introspect_validation_error_omits_access_token_input() -> None:
    """Verify introspection omits raw access_token validation inputs."""
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.post(
            "/v1/token/introspect",
            headers={"X-Request-Id": "req-introspect-redact"},
            json={"access_token": ["secret-token"]},
        )
    assert response.status_code == 422
    payload: dict[str, Any] = response.json()
    errors = payload["error"]["details"]["errors"]
    assert errors
    for error in errors:
        loc = error.get("loc", ())
        if isinstance(loc, (list, tuple)) and "access_token" in loc:
            assert "input" not in error


def test_service_uses_configured_verifier_thread_tokens() -> None:
    """Verify service exposes configured verifier thread-token limit."""
    service = TokenVerificationService(
        settings=Settings(OIDC_VERIFIER_THREAD_TOKENS=7)
    )
    assert service.verifier_thread_tokens == 7
