from __future__ import annotations

from typing import Any

import pytest
from nova_file_api.auth import (
    Authenticator,
    _bearer_auth_error,
)
from nova_file_api.cache import (
    LocalTTLCache,
    SharedRedisCache,
    TwoTierCache,
)
from nova_file_api.config import Settings
from nova_file_api.errors import FileTransferError
from oidc_jwt_verifier import AuthError


def _build_cache() -> TwoTierCache:
    return TwoTierCache(
        local=LocalTTLCache(ttl_seconds=60, max_entries=128),
        shared=SharedRedisCache(url=None),
        shared_ttl_seconds=60,
    )


class _VerifierReturningClaims:
    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.closed = False

    async def verify_access_token(self, token: str) -> dict[str, Any]:
        self.tokens.append(token)
        return {
            "sub": "subject-1",
            "scope_id": "scope-from-token",
            "scope": "uploads:write",
            "permissions": ["jobs:enqueue"],
        }

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_bearer_verification_uses_async_verifier_and_cache() -> None:
    settings = Settings()
    cache = _build_cache()
    auth = Authenticator(settings=settings, cache=cache)
    verifier = _VerifierReturningClaims()
    auth._verifier = verifier

    claims = await auth._verify_bearer_token(token="token-123")
    cached_claims = await auth._verify_bearer_token(token="token-123")

    assert claims["sub"] == "subject-1"
    assert cached_claims == claims
    assert verifier.tokens == ["token-123"]


@pytest.mark.anyio
async def test_authenticator_aclose_closes_async_verifier() -> None:
    settings = Settings()
    auth = Authenticator(settings=settings, cache=_build_cache())
    verifier = _VerifierReturningClaims()
    auth._verifier = verifier

    await auth.aclose()

    assert verifier.closed is True


@pytest.mark.anyio
async def test_bearer_auth_uses_principal_claim_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    auth = Authenticator(settings=settings, cache=_build_cache())

    async def _fake_verify_bearer_token(*, token: str) -> dict[str, Any]:
        del token
        return {
            "sub": "subject-1",
            "scope_id": "scope-from-token",
            "scope": "uploads:write",
        }

    monkeypatch.setattr(
        auth,
        "_verify_bearer_token",
        _fake_verify_bearer_token,
    )

    principal = await auth.authenticate(
        token="token-123",
    )
    assert principal.scope_id == "scope-from-token"


@pytest.mark.anyio
async def test_authenticate_requires_bearer_token() -> None:
    settings = Settings()
    auth = Authenticator(settings=settings, cache=_build_cache())

    with pytest.raises(FileTransferError) as exc:
        await auth.authenticate(token=None)
    assert exc.value.code == "unauthorized"
    assert exc.value.status_code == 401
    assert exc.value.message == "missing bearer token"
    assert "WWW-Authenticate" in exc.value.headers
    assert exc.value.headers["WWW-Authenticate"].startswith("Bearer")


def test_file_transfer_error_initializes_exception_message() -> None:
    exc = FileTransferError(
        code="invalid_request",
        message="invalid payload",
        status_code=422,
    )
    assert str(exc) == "invalid payload"
    assert exc.args == ("invalid payload",)


@pytest.mark.anyio
@pytest.mark.runtime_gate
async def test_required_scope_is_enforced_from_principal_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.oidc_required_scopes = "uploads:write"
    auth = Authenticator(settings=settings, cache=_build_cache())

    async def _fake_verify_bearer_token(*, token: str) -> dict[str, Any]:
        del token
        return {
            "sub": "subject-1",
            "scope_id": "scope-from-token",
            "scope": "uploads:read",
        }

    monkeypatch.setattr(
        auth,
        "_verify_bearer_token",
        _fake_verify_bearer_token,
    )

    with pytest.raises(FileTransferError) as exc:
        await auth.authenticate(token="token-123")
    assert exc.value.code == "forbidden"
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_required_permission_is_enforced_from_principal_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.oidc_required_permissions = "jobs:enqueue"
    auth = Authenticator(settings=settings, cache=_build_cache())

    async def _fake_verify_bearer_token(*, token: str) -> dict[str, Any]:
        del token
        return {
            "sub": "subject-1",
            "scope_id": "scope-from-token",
            "scope": "uploads:write",
            "permissions": ["jobs:read"],
        }

    monkeypatch.setattr(
        auth,
        "_verify_bearer_token",
        _fake_verify_bearer_token,
    )

    with pytest.raises(FileTransferError) as exc:
        await auth.authenticate(token="token-123")
    assert exc.value.code == "forbidden"
    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "code",
    [
        "invalid_issuer",
        "invalid_audience",
        "token_expired",
        "token_not_yet_valid",
    ],
)
@pytest.mark.runtime_gate
def test_bearer_auth_error_maps_common_jwt_claim_failures(
    code: str,
) -> None:
    error = AuthError(code=code, message="claim rejected", status_code=401)
    mapped = _bearer_auth_error(exc=error)
    assert mapped.code == code
    assert mapped.status_code == 401
    header = mapped.headers.get("WWW-Authenticate", "")
    assert header.startswith("Bearer ")
    assert 'error="invalid_token"' in header


def test_bearer_auth_error_maps_insufficient_scope_to_rfc6750() -> None:
    error = AuthError(
        code="insufficient_scope",
        message="missing required scopes",
        status_code=403,
        required_scopes=("uploads:write",),
    )
    mapped = _bearer_auth_error(exc=error)
    assert mapped.code == "insufficient_scope"
    assert mapped.status_code == 403
    header = mapped.headers.get("WWW-Authenticate", "")
    assert 'error="insufficient_scope"' in header
    assert "uploads:write" in header
