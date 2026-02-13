from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from nova_auth_api.app import create_app
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
        pass

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
    assert response.json() == {"ok": True}


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
