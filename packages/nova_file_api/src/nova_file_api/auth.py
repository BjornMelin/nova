"""Authentication and principal mapping logic."""

from __future__ import annotations

import time
from typing import Any, Protocol

from nova_runtime_support import (
    build_async_jwt_verifier,
    normalized_principal_claims,
)
from oidc_jwt_verifier import AuthError

from nova_file_api.cache import TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.errors import (
    FileTransferError,
    forbidden,
    unauthorized,
)
from nova_file_api.models import Principal


class AccessTokenVerifier(Protocol):
    """Structural interface for async JWT access-token verification."""

    async def verify_access_token(self, token: str) -> dict[str, Any]:
        """Verify one access token and return decoded claims."""

    async def aclose(self) -> None:
        """Release verifier-owned async resources."""


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

    async def authenticate(
        self,
        *,
        token: str | None,
    ) -> Principal:
        """Authenticate caller and return principal.

        Args:
            token: Bearer token extracted from the Authorization header.

        Raises:
            FileTransferError: On authentication or authorization failures.
        """
        normalized_token = token.strip() if isinstance(token, str) else ""
        if not normalized_token:
            raise unauthorized("missing bearer token")

        claims = await self._verify_local_token(token=normalized_token)

        principal = _principal_from_claims(claims=claims)
        self._enforce_required_authorization(principal=principal)
        return principal

    async def healthcheck(self) -> bool:
        """Return readiness of the active auth dependency."""
        return (
            self._settings.local_oidc_verifier_configured
            and self._verifier is not None
        )

    async def aclose(self) -> None:
        """Close verifier-owned async resources when configured."""
        verifier = self._verifier
        if verifier is None:
            return
        await verifier.aclose()

    async def _verify_local_token(self, *, token: str) -> dict[str, Any]:
        cache_key = self._cache.namespaced_key("jwt", token)
        cached = await self._cache.get_json(cache_key)
        if cached is not None:
            return cached

        verifier = self._verifier
        if verifier is None:
            raise unauthorized("local jwt mode is misconfigured")

        try:
            claims = await verifier.verify_access_token(token)
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
    def _build_verifier(settings: Settings) -> AccessTokenVerifier | None:
        return build_async_jwt_verifier(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            jwks_url=settings.oidc_jwks_url,
            clock_skew_seconds=settings.oidc_clock_skew_seconds,
        )


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
