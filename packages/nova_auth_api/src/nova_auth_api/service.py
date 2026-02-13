"""Token verification service implementation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import anyio
from oidc_jwt_verifier import AuthConfig, AuthError, JWTVerifier

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

    async def verify(self, request: TokenVerifyRequest) -> TokenVerifyResponse:
        """Verify access token and return principal plus claims."""
        scopes = (
            request.required_scopes
            if request.required_scopes is not None
            else self._settings.default_required_scopes
        )
        permissions = (
            request.required_permissions
            if request.required_permissions is not None
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
            if request.required_scopes is not None
            else self._settings.default_required_scopes
        )
        permissions = (
            request.required_permissions
            if request.required_permissions is not None
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
    issuer = settings.oidc_issuer
    audience = settings.oidc_audience
    jwks_url = settings.oidc_jwks_url
    if issuer is None or audience is None or jwks_url is None:
        return None
    config = AuthConfig(
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        required_scopes=settings.default_required_scopes,
        required_permissions=settings.default_required_permissions,
        leeway_s=settings.oidc_clock_skew_seconds,
    )
    return JWTVerifier(config=config)


def _principal_from_claims(*, claims: dict[str, Any]) -> Principal:
    subject = _claim_as_str(claims=claims, keys=("sub",))
    if subject is None:
        raise unauthorized(
            "token subject claim is missing",
            www_authenticate='Bearer error="invalid_token"',
        )

    tenant_id = _claim_as_str(claims=claims, keys=("tenant_id", "org_id"))
    scope_id = (
        _claim_as_str(claims=claims, keys=("scope_id",)) or tenant_id or subject
    )

    return Principal(
        subject=subject,
        scope_id=scope_id,
        tenant_id=tenant_id,
        scopes=tuple(_collect_string_claim(claims.get("scope"))),
        permissions=tuple(_collect_string_claim(claims.get("permissions"))),
    )


def _claim_as_str(*, claims: dict[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _collect_string_claim(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [segment for segment in value.split(" ") if segment]
    if isinstance(value, (list, tuple)):
        values: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                values.append(item.strip())
        return values
    raise AuthApiError(
        code="invalid_token",
        message="token claim type is invalid",
        status_code=401,
    )
