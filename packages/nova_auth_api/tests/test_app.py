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


def test_healthz() -> None:
    app = create_app(service_override=_StubService())
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "nova-auth-api"
    assert isinstance(payload["request_id"], str)
    assert payload["request_id"]


def test_verify_endpoint() -> None:
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


def test_verify_validation_error_uses_canonical_error_envelope() -> None:
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
