# ruff: noqa: I001

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from typing import cast

import pytest
from nova_auth_api.config import Settings
from nova_auth_api.models import (
    Principal,
    TokenIntrospectRequest,
    TokenVerifyRequest,
)
from nova_auth_api.service import TokenVerificationService, _build_verifier


def _principal() -> Principal:
    return Principal(
        subject="subject-1",
        scope_id="scope-1",
        tenant_id=None,
        scopes=("uploads:write",),
        permissions=("jobs:enqueue",),
    )


class _VerifierAssertingThreadBoundary:
    def __init__(self, state: dict[str, bool]) -> None:
        self._state = state
        self.calls = 0

    def verify_access_token(self, token: str) -> dict[str, Any]:
        assert self._state["inside_run_sync"]
        self.calls += 1
        del token
        return {"sub": "subject-1"}


@pytest.mark.asyncio
async def test_verify_uses_defaults_when_override_fields_are_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.oidc_required_scopes = "uploads:write"
    settings.oidc_required_permissions = "jobs:enqueue"
    service = TokenVerificationService(settings=settings)
    captured: dict[str, tuple[str, ...]] = {}

    async def _fake_verify_claims(
        *,
        access_token: str,
        required_scopes: tuple[str, ...],
        required_permissions: tuple[str, ...],
    ) -> tuple[Principal, dict[str, Any]]:
        del access_token
        captured["required_scopes"] = required_scopes
        captured["required_permissions"] = required_permissions
        return _principal(), {"sub": "subject-1"}

    monkeypatch.setattr(service, "_verify_claims", _fake_verify_claims)

    response = await service.verify(TokenVerifyRequest(access_token="token"))

    assert response.principal.subject == "subject-1"
    assert captured["required_scopes"] == ("uploads:write",)
    assert captured["required_permissions"] == ("jobs:enqueue",)


@pytest.mark.asyncio
async def test_introspect_respects_explicit_empty_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.oidc_required_scopes = "uploads:write"
    settings.oidc_required_permissions = "jobs:enqueue"
    service = TokenVerificationService(settings=settings)
    captured: dict[str, tuple[str, ...]] = {}

    async def _fake_verify_claims(
        *,
        access_token: str,
        required_scopes: tuple[str, ...],
        required_permissions: tuple[str, ...],
    ) -> tuple[Principal, dict[str, Any]]:
        del access_token
        captured["required_scopes"] = required_scopes
        captured["required_permissions"] = required_permissions
        return _principal(), {"sub": "subject-1"}

    monkeypatch.setattr(service, "_verify_claims", _fake_verify_claims)

    response = await service.introspect(
        TokenIntrospectRequest(
            access_token="token",
            required_scopes=(),
            required_permissions=(),
        )
    )

    assert response.active is True
    assert captured["required_scopes"] == ()
    assert captured["required_permissions"] == ()


@pytest.mark.asyncio
async def test_verify_runs_sync_jwt_verification_via_thread_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify synchronous JWT verification runs via a thread boundary.

    Args:
        monkeypatch: Fixture used to patch thread-boundary execution.

    Returns:
        None.
    """
    settings = Settings()
    service = TokenVerificationService(settings=settings)
    boundary_state = {"inside_run_sync": False}
    verifier = _VerifierAssertingThreadBoundary(boundary_state)
    service._verifier = cast(Any, verifier)

    run_sync_calls = 0

    async def _run_sync(
        func: Callable[[str], dict[str, Any]],
        access_token: str,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal run_sync_calls
        run_sync_calls += 1
        boundary_state["inside_run_sync"] = True
        try:
            return func(access_token)
        finally:
            boundary_state["inside_run_sync"] = False

    monkeypatch.setattr(
        "nova_auth_api.service.anyio.to_thread.run_sync", _run_sync
    )

    response = await service.verify(TokenVerifyRequest(access_token="token-1"))

    assert response.principal.subject == "subject-1"
    assert run_sync_calls == 1
    assert verifier.calls == 1


def test_build_verifier_does_not_embed_default_authorization_requirements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.oidc_issuer = "https://issuer.example.com/"
    settings.oidc_audience = "api://nova"
    settings.oidc_jwks_url = "https://issuer.example.com/.well-known/jwks.json"
    settings.oidc_required_scopes = "uploads:write"
    settings.oidc_required_permissions = "jobs:enqueue"
    captured: dict[str, Any] = {}

    class _DummyVerifier:
        def __init__(self, config: Any) -> None:
            captured["config"] = config

    monkeypatch.setattr("nova_auth_api.service.JWTVerifier", _DummyVerifier)

    verifier = _build_verifier(settings=settings)

    assert verifier is not None
    config = captured["config"]
    assert config.required_scopes == ()
    assert config.required_permissions == ()
