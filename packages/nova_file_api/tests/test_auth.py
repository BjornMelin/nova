from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import httpx
import pytest
from nova_file_api.auth import (
    Authenticator,
    _local_auth_error,
)
from nova_file_api.cache import (
    LocalTTLCache,
    SharedRedisCache,
    TwoTierCache,
)
from nova_file_api.config import Settings
from nova_file_api.errors import FileTransferError
from nova_file_api.models import AuthMode
from oidc_jwt_verifier import AuthError, JWTVerifier
from starlette.requests import Request


def _build_request(*, headers: dict[str, str]) -> Request:
    raw_headers = [
        (key.lower().encode("utf-8"), value.encode("utf-8"))
        for key, value in headers.items()
    ]
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/v1/jobs",
        "raw_path": b"/v1/jobs",
        "query_string": b"",
        "headers": raw_headers,
        "client": ("127.0.0.1", 0),
        "server": ("testserver", 443),
    }
    return Request(scope=scope)


def _build_cache() -> TwoTierCache:
    return TwoTierCache(
        local=LocalTTLCache(ttl_seconds=60, max_entries=128),
        shared=SharedRedisCache(url=None),
        shared_ttl_seconds=60,
    )


class _VerifierReturningClaims:
    def verify_access_token(self, token: str) -> dict[str, Any]:
        del token
        return {
            "sub": "subject-1",
            "scope_id": "scope-from-token",
            "scope": "uploads:write",
            "permissions": ["jobs:enqueue"],
        }


class _FailingRemoteAuthClient:
    def __init__(self, *, timeout: float) -> None:
        del timeout

    async def __aenter__(self) -> _FailingRemoteAuthClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        del exc_type, exc, tb

    async def post(self, url: str, json: dict[str, Any]) -> httpx.Response:
        del json
        request = httpx.Request("POST", url)
        raise httpx.ConnectError("connect failed", request=request)


class _RejectedRemoteAuthClient:
    def __init__(self, *, timeout: float) -> None:
        del timeout

    async def __aenter__(self) -> _RejectedRemoteAuthClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        del exc_type, exc, tb

    async def post(self, url: str, json: dict[str, Any]) -> httpx.Response:
        del url, json
        return httpx.Response(
            401,
            headers={
                "WWW-Authenticate": (
                    'Bearer error="invalid_token",'
                    ' error_description="bad token"'
                )
            },
            json={
                "error": {
                    "code": "unauthorized",
                    "message": "bad token",
                }
            },
        )


@pytest.mark.asyncio
async def test_local_verification_uses_thread_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.auth_mode = AuthMode.JWT_LOCAL
    cache = _build_cache()
    auth = Authenticator(settings=settings, cache=cache)
    auth._verifier = cast(JWTVerifier, _VerifierReturningClaims())

    call_count = {"count": 0}

    async def _run_sync(
        func: Callable[[str], dict[str, Any]],
        token: str,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        call_count["count"] += 1
        return func(token)

    monkeypatch.setattr(
        "nova_file_api.auth.anyio.to_thread.run_sync",
        _run_sync,
    )

    claims = await auth._verify_local_token(token="token-123")

    assert claims["sub"] == "subject-1"
    assert call_count["count"] == 1


@pytest.mark.asyncio
async def test_jwt_mode_prefers_principal_claim_scope_over_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.auth_mode = AuthMode.JWT_LOCAL
    auth = Authenticator(settings=settings, cache=_build_cache())

    async def _fake_verify_local_token(*, token: str) -> dict[str, Any]:
        del token
        return {
            "sub": "subject-1",
            "scope_id": "scope-from-token",
            "scope": "uploads:write",
        }

    monkeypatch.setattr(auth, "_verify_local_token", _fake_verify_local_token)

    principal = await auth.authenticate(
        request=_build_request(headers={"Authorization": "Bearer token-123"}),
        session_id="scope-from-session",
    )
    assert principal.scope_id == "scope-from-token"


@pytest.mark.asyncio
async def test_same_origin_prefers_session_header_precedence() -> None:
    settings = Settings()
    settings.auth_mode = AuthMode.SAME_ORIGIN
    auth = Authenticator(settings=settings, cache=_build_cache())

    principal = await auth.authenticate(
        request=_build_request(
            headers={
                "X-Session-Id": "scope-from-session-header",
                "X-Scope-Id": "scope-from-legacy-header",
            }
        ),
        session_id="scope-from-session-header",
    )

    assert principal.scope_id == "scope-from-session-header"


@pytest.mark.asyncio
async def test_same_origin_rejects_conflicting_session_scope() -> None:
    settings = Settings()
    settings.auth_mode = AuthMode.SAME_ORIGIN
    auth = Authenticator(settings=settings, cache=_build_cache())

    with pytest.raises(FileTransferError) as exc:
        await auth.authenticate(
            request=_build_request(
                headers={"X-Session-Id": "scope-from-session-header"}
            ),
            session_id="scope-from-body",
        )
    assert exc.value.code == "invalid_request"
    assert exc.value.status_code == 422
    assert exc.value.message == "conflicting session scope"


@pytest.mark.asyncio
async def test_same_origin_rejects_legacy_header_body_conflict() -> None:
    settings = Settings()
    settings.auth_mode = AuthMode.SAME_ORIGIN
    auth = Authenticator(settings=settings, cache=_build_cache())

    with pytest.raises(FileTransferError) as exc:
        await auth.authenticate(
            request=_build_request(
                headers={"X-Scope-Id": "scope-from-legacy-header"}
            ),
            session_id="scope-from-body",
        )
    assert exc.value.code == "unauthorized"
    assert exc.value.status_code == 401
    assert exc.value.message == "conflicting session scope"


def test_file_transfer_error_initializes_exception_message() -> None:
    exc = FileTransferError(
        code="invalid_request",
        message="invalid payload",
        status_code=422,
    )
    assert str(exc) == "invalid payload"
    assert exc.args == ("invalid payload",)


@pytest.mark.asyncio
async def test_required_scope_is_enforced_from_principal_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.auth_mode = AuthMode.JWT_LOCAL
    settings.oidc_required_scopes = "uploads:write"
    auth = Authenticator(settings=settings, cache=_build_cache())

    async def _fake_verify_local_token(*, token: str) -> dict[str, Any]:
        del token
        return {
            "sub": "subject-1",
            "scope_id": "scope-from-token",
            "scope": "uploads:read",
        }

    monkeypatch.setattr(auth, "_verify_local_token", _fake_verify_local_token)

    with pytest.raises(FileTransferError) as exc:
        await auth.authenticate(
            request=_build_request(
                headers={"Authorization": "Bearer token-123"}
            ),
            session_id=None,
        )
    assert exc.value.code == "forbidden"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_required_permission_is_enforced_from_principal_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.auth_mode = AuthMode.JWT_LOCAL
    settings.oidc_required_permissions = "jobs:enqueue"
    auth = Authenticator(settings=settings, cache=_build_cache())

    async def _fake_verify_local_token(*, token: str) -> dict[str, Any]:
        del token
        return {
            "sub": "subject-1",
            "scope_id": "scope-from-token",
            "scope": "uploads:write",
            "permissions": ["jobs:read"],
        }

    monkeypatch.setattr(auth, "_verify_local_token", _fake_verify_local_token)

    with pytest.raises(FileTransferError) as exc:
        await auth.authenticate(
            request=_build_request(
                headers={"Authorization": "Bearer token-123"}
            ),
            session_id=None,
        )
    assert exc.value.code == "forbidden"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_remote_auth_mode_fails_closed_on_http_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.auth_mode = AuthMode.JWT_REMOTE
    settings.remote_auth_base_url = "https://auth.example.local"
    auth = Authenticator(settings=settings, cache=_build_cache())

    monkeypatch.setattr(
        "nova_file_api.auth.httpx.AsyncClient", _FailingRemoteAuthClient
    )

    with pytest.raises(FileTransferError) as exc:
        await auth.authenticate(
            request=_build_request(
                headers={"Authorization": "Bearer token-123"}
            ),
            session_id=None,
        )
    assert exc.value.code == "queue_unavailable"
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_remote_auth_401_propagates_www_authenticate_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.auth_mode = AuthMode.JWT_REMOTE
    settings.remote_auth_base_url = "https://auth.example.local"
    auth = Authenticator(settings=settings, cache=_build_cache())

    monkeypatch.setattr(
        "nova_file_api.auth.httpx.AsyncClient", _RejectedRemoteAuthClient
    )

    with pytest.raises(FileTransferError) as exc:
        await auth.authenticate(
            request=_build_request(
                headers={"Authorization": "Bearer token-123"}
            ),
            session_id=None,
        )
    assert exc.value.code == "unauthorized"
    assert exc.value.status_code == 401
    assert exc.value.headers.get("WWW-Authenticate", "").startswith("Bearer ")


@pytest.mark.parametrize(
    "code",
    [
        "invalid_issuer",
        "invalid_audience",
        "token_expired",
        "token_not_yet_valid",
    ],
)
def test_local_auth_error_maps_common_jwt_claim_failures(code: str) -> None:
    error = AuthError(code=code, message="claim rejected", status_code=401)
    mapped = _local_auth_error(exc=error)
    assert mapped.code == code
    assert mapped.status_code == 401
    header = mapped.headers.get("WWW-Authenticate", "")
    assert header.startswith("Bearer ")
    assert 'error="invalid_token"' in header


def test_local_auth_error_maps_insufficient_scope_to_rfc6750() -> None:
    error = AuthError(
        code="insufficient_scope",
        message="missing required scopes",
        status_code=403,
        required_scopes=("uploads:write",),
    )
    mapped = _local_auth_error(exc=error)
    assert mapped.code == "insufficient_scope"
    assert mapped.status_code == 403
    header = mapped.headers.get("WWW-Authenticate", "")
    assert 'error="insufficient_scope"' in header
    assert "uploads:write" in header
