"""Token verification service implementation."""

from __future__ import annotations

from typing import Any

import anyio
from nova_runtime_support import build_jwt_verifier, normalized_principal_claims
from oidc_jwt_verifier import AuthError, JWTVerifier

from nova_auth_api.config import Settings
from nova_auth_api.errors import (
    AuthApiError,
    forbidden,
    from_oidc_auth_error,
    unauthorized,
)
from nova_auth_api.models import (
    Principal,
    TokenIntrospectRequest,
    TokenIntrospectResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
)


class TokenVerificationService:
    """Verify and introspect JWT access tokens."""

    def __init__(self, *, settings: Settings) -> None:
        """Initialize service state."""
        self._settings = settings
        self._verifier = _build_verifier(settings=settings)
        self._thread_limiter = anyio.CapacityLimiter(
            settings.oidc_verifier_thread_tokens
        )

    async def verify(self, request: TokenVerifyRequest) -> TokenVerifyResponse:
        """Verify access token and return principal plus claims."""
        scopes = (
            request.required_scopes
            if "required_scopes" in request.model_fields_set
            else self._settings.default_required_scopes
        )
        permissions = (
            request.required_permissions
            if "required_permissions" in request.model_fields_set
            else self._settings.default_required_permissions
        )
        principal, claims = await self._verify_claims(
            access_token=request.access_token,
            required_scopes=scopes,
            required_permissions=permissions,
        )
        return TokenVerifyResponse(principal=principal, claims=claims)

    async def introspect(
        self,
        request: TokenIntrospectRequest,
    ) -> TokenIntrospectResponse:
        """Introspect access token and return active principal metadata."""
        scopes = (
            request.required_scopes
            if "required_scopes" in request.model_fields_set
            else self._settings.default_required_scopes
        )
        permissions = (
            request.required_permissions
            if "required_permissions" in request.model_fields_set
            else self._settings.default_required_permissions
        )
        principal, claims = await self._verify_claims(
            access_token=request.access_token,
            required_scopes=scopes,
            required_permissions=permissions,
        )
        return TokenIntrospectResponse(
            active=True,
            principal=principal,
            claims=claims,
        )

    def is_ready(self) -> bool:
        """Return whether token verification is currently usable."""
        return self._verifier is not None

    @property
    def verifier_thread_tokens(self) -> int:
        """Return configured thread tokens for verifier execution."""
        return self._settings.oidc_verifier_thread_tokens

    async def _verify_claims(
        self,
        *,
        access_token: str,
        required_scopes: tuple[str, ...],
        required_permissions: tuple[str, ...],
    ) -> tuple[Principal, dict[str, Any]]:
        verifier = self._verifier
        if verifier is None:
            raise unauthorized(
                "auth verifier unavailable",
                www_authenticate='Bearer error="invalid_token"',
            )
        try:
            claims = await anyio.to_thread.run_sync(
                verifier.verify_access_token,
                access_token,
                limiter=self._thread_limiter,
            )
        except AuthError as exc:
            raise from_oidc_auth_error(exc) from exc

        principal = _principal_from_claims(claims=claims)
        if required_scopes and not set(required_scopes).issubset(
            set(principal.scopes)
        ):
            raise forbidden("missing required scopes")
        if required_permissions and not set(required_permissions).issubset(
            set(principal.permissions)
        ):
            raise forbidden("missing required permissions")
        return principal, claims


def _build_verifier(*, settings: Settings) -> JWTVerifier | None:
    if not settings.local_oidc_verifier_configured:
        return None
    return build_jwt_verifier(
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        jwks_url=settings.oidc_jwks_url,
        clock_skew_seconds=settings.oidc_clock_skew_seconds,
    )


def _principal_from_claims(*, claims: dict[str, Any]) -> Principal:
    normalized = normalized_principal_claims(
        claims=claims,
        invalid_token_error=_invalid_token_error,
    )
    return Principal(
        subject=normalized.subject,
        scope_id=normalized.scope_id,
        tenant_id=normalized.tenant_id,
        scopes=normalized.scopes,
        permissions=normalized.permissions,
    )


def _invalid_token_error(message: str) -> AuthApiError:
    return AuthApiError(
        code="invalid_token",
        message=message,
        status_code=401,
        headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
    )
