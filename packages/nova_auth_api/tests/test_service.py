from __future__ import annotations

from typing import Any

import pytest
from nova_auth_api.config import Settings
from nova_auth_api.models import (
    Principal,
    TokenIntrospectRequest,
    TokenVerifyRequest,
)
from nova_auth_api.service import TokenVerificationService


def _principal() -> Principal:
    return Principal(
        subject="subject-1",
        scope_id="scope-1",
        tenant_id=None,
        scopes=("uploads:write",),
        permissions=("jobs:enqueue",),
    )


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
