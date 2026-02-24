"""Authentication and principal mapping logic."""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import anyio
import httpx
from oidc_jwt_verifier import AuthConfig, AuthError, JWTVerifier
from starlette.requests import Request

from nova_file_api.cache import TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.errors import (
    FileTransferError,
    forbidden,
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
        self._thread_limiter: Any | None = None

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

        thread_limiter = self._thread_limiter
        if thread_limiter is None:
            thread_limiter = _jwt_verifier_thread_limiter()
            self._thread_limiter = thread_limiter

        try:
            # Default AnyIO worker pool is token-limited; tune
            # OIDC_VERIFIER_THREAD_TOKENS via settings for expected load.
            claims = await anyio.to_thread.run_sync(
                verifier.verify_access_token,
                token,
                limiter=thread_limiter,
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
        timeout = self._settings.remote_auth_timeout_seconds

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise unauthorized("remote auth verification failed") from exc

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
        if (
            settings.oidc_issuer is None
            or settings.oidc_audience is None
            or settings.oidc_jwks_url is None
        ):
            return None
        config = AuthConfig(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            jwks_url=settings.oidc_jwks_url,
            required_scopes=settings.default_required_scopes,
            required_permissions=settings.default_required_permissions,
            leeway_s=settings.oidc_clock_skew_seconds,
        )
        return JWTVerifier(config=config)


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
    subject_raw = claims.get("sub")
    if not isinstance(subject_raw, str) or not subject_raw.strip():
        raise unauthorized("token subject claim is missing")

    tenant_value = _claim_as_str(claims=claims, keys=("tenant_id", "org_id"))
    scope_value = _claim_as_str(claims=claims, keys=("scope_id",))
    scope_id = scope_value or tenant_value or subject_raw

    scopes = _collect_string_claim(claims.get("scope"))
    permissions = _collect_string_claim(claims.get("permissions"))

    return Principal(
        subject=subject_raw,
        scope_id=scope_id,
        tenant_id=tenant_value,
        scopes=tuple(scopes),
        permissions=tuple(permissions),
    )


def _claim_as_str(*, claims: dict[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _jwt_verifier_thread_limiter() -> Any:
    """Return the runtime AnyIO thread limiter used for verifier work."""
    return anyio.to_thread.current_default_thread_limiter()


def _set_verifier_thread_tokens(total_tokens: int) -> None:
    """Set process-wide verifier thread capacity for sync JWT verification.

    The default AnyIO thread-limiter protects event-loop liveness while running
    CPU-bound or blocking verification steps in a worker pool.
    """
    limiter = _jwt_verifier_thread_limiter()
    limiter.total_tokens = total_tokens


def _collect_string_claim(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [
            segment.strip() for segment in value.split(" ") if segment.strip()
        ]
    if isinstance(value, (list, tuple)):
        output: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                output.append(item.strip())
        return output
    # File API surfaces FileTransferError in its canonical response envelope.
    raise FileTransferError(
        code="invalid_token",
        message="token claim type is invalid",
        status_code=401,
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
    if status_code not in {401, 403}:
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
    subject = _claim_as_str(claims=principal, keys=("subject", "sub"))
    if subject is None:
        raise unauthorized("remote auth principal is missing subject")

    tenant_id = _claim_as_str(claims=principal, keys=("tenant_id", "org_id"))
    scope_id = (
        _claim_as_str(claims=principal, keys=("scope_id",))
        or tenant_id
        or subject
    )
    scopes = _collect_string_claim(principal.get("scopes"))
    permissions = _collect_string_claim(principal.get("permissions"))
    return Principal(
        subject=subject,
        scope_id=scope_id,
        tenant_id=tenant_id,
        scopes=tuple(scopes),
        permissions=tuple(permissions),
    )


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
