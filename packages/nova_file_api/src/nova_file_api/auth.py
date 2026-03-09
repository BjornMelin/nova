"""Authentication and principal mapping logic."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import anyio
import httpx
from anyio.abc import CapacityLimiter
from nova_runtime_support import build_jwt_verifier, normalized_principal_claims
from oidc_jwt_verifier import AuthError, JWTVerifier
from starlette.requests import Request

from nova_file_api.cache import TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.errors import (
    FileTransferError,
    forbidden,
    invalid_request,
    service_unavailable,
    unauthorized,
)
from nova_file_api.models import AuthMode, Principal


class Authenticator:
    """Resolve and validate principals based on configured auth mode."""

    def __init__(self, *, settings: Settings, cache: TwoTierCache) -> None:
        """Initialize authenticator state and optional JWT verifier.

        Args:
            settings: Runtime authentication settings.
            cache: Shared cache for token verification results.
        """
        self._settings = settings
        self._cache = cache
        self._verifier = self._build_verifier(settings)
        self._verifier_thread_limiter: CapacityLimiter = anyio.CapacityLimiter(
            settings.oidc_verifier_thread_tokens
        )
        self._remote_client: httpx.AsyncClient | None = None
        self._remote_client_lock = asyncio.Lock()

    async def authenticate(
        self,
        *,
        request: Request,
        session_id: str | None,
    ) -> Principal:
        """Authenticate caller and return principal.

        Args:
            request: Current request with headers.
            session_id: Optional body-provided session identifier.

        Raises:
            FileTransferError: On authentication or authorization failures.
        """
        if self._settings.auth_mode == AuthMode.SAME_ORIGIN:
            return self._same_origin_principal(
                request=request, session_id=session_id
            )

        token = _extract_bearer_token(request=request)
        if token is None:
            raise unauthorized("missing bearer token")

        if self._settings.auth_mode == AuthMode.JWT_REMOTE:
            principal = await self._verify_remote_principal(token=token)
            self._enforce_required_authorization(principal=principal)
            return principal
        else:
            claims = await self._verify_local_token(token=token)

        principal = _principal_from_claims(claims=claims)
        self._enforce_required_authorization(principal=principal)
        return principal

    async def healthcheck(self) -> bool:
        """Return readiness of the active auth dependency."""
        if self._settings.auth_mode == AuthMode.SAME_ORIGIN:
            return True
        if self._settings.auth_mode == AuthMode.JWT_LOCAL:
            return self._verifier is not None

        base_url = self._settings.remote_auth_base_url
        if base_url is None:
            return False

        url = f"{base_url.rstrip('/')}/v1/health/ready"
        try:
            client = await self._get_remote_client()
            response = await client.get(url)
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    async def aclose(self) -> None:
        """Close any lazily-initialized remote auth client."""
        client = self._remote_client
        if client is None:
            return
        self._remote_client = None
        await client.aclose()

    def _same_origin_principal(
        self,
        *,
        request: Request,
        session_id: str | None,
    ) -> Principal:
        header_session_id = request.headers.get("X-Session-Id")
        header_scope_id = request.headers.get("X-Scope-Id")
        session_scope = (
            header_session_id.strip()
            if header_session_id is not None and header_session_id.strip()
            else None
        )
        body_scope = (
            session_id.strip()
            if session_id is not None and session_id.strip()
            else None
        )
        legacy_scope = (
            header_scope_id.strip()
            if header_scope_id is not None and header_scope_id.strip()
            else None
        )
        if (
            session_scope is not None
            and body_scope is not None
            and session_scope != body_scope
        ):
            raise invalid_request("conflicting session scope")
        if (
            session_scope is None
            and legacy_scope is not None
            and body_scope is not None
            and legacy_scope != body_scope
        ):
            raise unauthorized("conflicting session scope")
        raw_scope = session_scope or body_scope or legacy_scope
        if raw_scope is None:
            raise unauthorized("missing session scope")
        return Principal(subject=raw_scope, scope_id=raw_scope)

    async def _verify_local_token(self, *, token: str) -> dict[str, Any]:
        cache_key = self._cache.namespaced_key("jwt", token)
        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            return cached

        verifier = self._verifier
        if verifier is None:
            raise unauthorized("local jwt mode is misconfigured")

        try:
            claims = await anyio.to_thread.run_sync(
                verifier.verify_access_token,
                token,
                limiter=self._verifier_thread_limiter,
            )
        except AuthError as exc:
            raise _local_auth_error(exc=exc) from exc

        ttl_seconds = _jwt_cache_ttl_seconds(
            claims=claims,
            clock_skew_seconds=self._settings.oidc_clock_skew_seconds,
            max_ttl_seconds=self._settings.auth_jwt_cache_max_ttl_seconds,
        )
        if ttl_seconds > 0:
            await self._cache.set_json(
                cache_key,
                claims,
                ttl_seconds=ttl_seconds,
            )
        return claims

    async def _verify_remote_principal(self, *, token: str) -> Principal:
        base_url = self._settings.remote_auth_base_url
        if base_url is None:
            raise unauthorized("remote auth mode is misconfigured")

        url = f"{base_url.rstrip('/')}/v1/token/verify"
        payload = {
            "access_token": token,
            "required_scopes": list(self._settings.default_required_scopes),
            "required_permissions": list(
                self._settings.default_required_permissions
            ),
        }
        try:
            client = await self._get_remote_client()
            response = await client.post(
                url,
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise service_unavailable(
                "remote auth verification unavailable"
            ) from exc

        if response.status_code != 200:
            raise _remote_auth_error(response=response)

        try:
            decoded = response.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise unauthorized("remote auth returned invalid response") from exc
        if not isinstance(decoded, dict):
            raise unauthorized("remote auth returned invalid response")

        principal_raw = decoded.get("principal")
        if isinstance(principal_raw, dict):
            return _principal_from_remote_payload(principal=principal_raw)

        claims_raw = decoded.get("claims", decoded.get("token", decoded))
        if not isinstance(claims_raw, dict):
            raise unauthorized("remote auth claims payload is invalid")
        return _principal_from_claims(claims=claims_raw)

    def _enforce_required_authorization(self, *, principal: Principal) -> None:
        required_scopes = set(self._settings.default_required_scopes)
        if required_scopes and not required_scopes.issubset(
            set(principal.scopes)
        ):
            raise forbidden("missing required scopes")

        required_permissions = set(self._settings.default_required_permissions)
        if required_permissions and not required_permissions.issubset(
            set(principal.permissions)
        ):
            raise forbidden("missing required permissions")

    @staticmethod
    def _build_verifier(settings: Settings) -> JWTVerifier | None:
        if settings.auth_mode != AuthMode.JWT_LOCAL:
            return None
        return build_jwt_verifier(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            jwks_url=settings.oidc_jwks_url,
            clock_skew_seconds=settings.oidc_clock_skew_seconds,
            required_scopes=settings.default_required_scopes,
            required_permissions=settings.default_required_permissions,
        )

    async def _get_remote_client(self) -> httpx.AsyncClient:
        client = self._remote_client
        if client is not None:
            return client
        async with self._remote_client_lock:
            client = self._remote_client
            if client is not None:
                return client
            client = httpx.AsyncClient(
                timeout=self._settings.remote_auth_timeout_seconds
            )
            self._remote_client = client
            return client


def _extract_bearer_token(*, request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header is None:
        return None
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None
    return token


def _principal_from_claims(*, claims: dict[str, Any]) -> Principal:
    normalized = normalized_principal_claims(
        claims=claims,
        invalid_token_error=unauthorized,
    )
    return Principal(
        subject=normalized.subject,
        scope_id=normalized.scope_id,
        tenant_id=normalized.tenant_id,
        scopes=normalized.scopes,
        permissions=normalized.permissions,
    )


def _local_auth_error(*, exc: AuthError) -> FileTransferError:
    code_value = getattr(exc, "code", "invalid_token")
    message_value = getattr(exc, "message", "token validation failed")
    status_value = getattr(exc, "status_code", 401)
    code = code_value if isinstance(code_value, str) else "invalid_token"
    message = (
        message_value
        if isinstance(message_value, str)
        else "token validation failed"
    )
    status_code = status_value if isinstance(status_value, int) else 401
    header_value = _www_authenticate_from_auth_error(exc=exc)
    headers: dict[str, str] = {}
    if header_value is not None:
        headers["WWW-Authenticate"] = header_value
    return FileTransferError(
        code=code,
        message=message,
        status_code=status_code,
        headers=headers,
    )


def _www_authenticate_from_auth_error(*, exc: AuthError) -> str | None:
    method = getattr(exc, "www_authenticate_header", None)
    if not callable(method):
        return None
    try:
        value = method()
    except (ValueError, TypeError, RuntimeError):
        return None
    if isinstance(value, str) and value:
        return value
    return None


def _remote_auth_error(*, response: httpx.Response) -> FileTransferError:
    body = _safe_json_dict(response=response)
    error_payload = body.get("error")
    code = "unauthorized"
    message = "remote auth rejected token"
    if isinstance(error_payload, dict):
        code_value = error_payload.get("code")
        message_value = error_payload.get("message")
        if isinstance(code_value, str) and code_value:
            code = code_value
        if isinstance(message_value, str) and message_value:
            message = message_value

    status_code = response.status_code
    if status_code == 403 and code == "unauthorized":
        code = "forbidden"
    if status_code >= 500:
        code = "auth_unavailable"
        status_code = 503
        message = "remote auth verification unavailable"
    elif status_code not in {401, 403}:
        status_code = 401

    headers: dict[str, str] = {}
    header_value = response.headers.get("WWW-Authenticate")
    if header_value:
        headers["WWW-Authenticate"] = header_value
    return FileTransferError(
        code=code,
        message=message,
        status_code=status_code,
        headers=headers,
    )


def _safe_json_dict(*, response: httpx.Response) -> dict[str, Any]:
    try:
        decoded = response.json()
    except (ValueError, UnicodeDecodeError):
        return {}
    if isinstance(decoded, dict):
        return decoded
    return {}


def _principal_from_remote_payload(*, principal: dict[str, Any]) -> Principal:
    normalized = normalized_principal_claims(
        claims=principal,
        invalid_token_error=_remote_principal_error,
        subject_keys=("subject", "sub"),
        scopes_claim="scopes",
    )
    return Principal(
        subject=normalized.subject,
        scope_id=normalized.scope_id,
        tenant_id=normalized.tenant_id,
        scopes=normalized.scopes,
        permissions=normalized.permissions,
    )


def _remote_principal_error(message: str) -> FileTransferError:
    return unauthorized(f"remote auth principal is invalid: {message}")


def _jwt_cache_ttl_seconds(
    *,
    claims: dict[str, Any],
    clock_skew_seconds: int,
    max_ttl_seconds: int,
) -> int:
    """Derive JWT cache TTL from exp claim with bounded maximum."""
    raw_exp = claims.get("exp")
    if isinstance(raw_exp, int):
        exp_epoch = raw_exp
    elif isinstance(raw_exp, float) or (
        isinstance(raw_exp, str) and raw_exp.isdigit()
    ):
        exp_epoch = int(raw_exp)
    else:
        return max_ttl_seconds

    now_epoch = int(time.time())
    remaining = exp_epoch - now_epoch - max(clock_skew_seconds, 0)
    if remaining <= 0:
        return 0
    return min(remaining, max_ttl_seconds)
