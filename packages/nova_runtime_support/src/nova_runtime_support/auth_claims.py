"""Shared JWT verifier and principal-claim normalization helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from oidc_jwt_verifier import AuthConfig
from oidc_jwt_verifier.async_verifier import AsyncJWTVerifier


@dataclass(frozen=True, slots=True)
class NormalizedPrincipalClaims:
    """Normalized principal fields extracted from a JWT-like payload."""

    subject: str
    scope_id: str
    tenant_id: str | None
    scopes: tuple[str, ...]
    permissions: tuple[str, ...]


InvalidTokenErrorFactory = Callable[[str], Exception]


def build_auth_config(
    *,
    issuer: str | None,
    audience: str | None,
    jwks_url: str | None,
    clock_skew_seconds: int,
) -> AuthConfig | None:
    """Build verifier config when required OIDC settings are present.

    Args:
        issuer: OIDC issuer URL.
        audience: Expected JWT audience.
        jwks_url: JWKS endpoint URL.
        clock_skew_seconds: Allowed verification clock skew in seconds.

    Returns:
        A configured ``AuthConfig`` when issuer, audience, and jwks_url are all
        set; otherwise ``None``.
    """
    issuer = _normalized_optional_setting(issuer)
    audience = _normalized_optional_setting(audience)
    jwks_url = _normalized_optional_setting(jwks_url)
    if issuer is None or audience is None or jwks_url is None:
        return None
    return AuthConfig(
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        leeway_s=clock_skew_seconds,
    )


def build_async_jwt_verifier(
    *,
    issuer: str | None,
    audience: str | None,
    jwks_url: str | None,
    clock_skew_seconds: int,
) -> AsyncJWTVerifier | None:
    """Build an async JWT verifier when required OIDC settings are present.

    Args:
        issuer: OIDC issuer URL.
        audience: Expected JWT audience.
        jwks_url: JWKS endpoint URL.
        clock_skew_seconds: Allowed verification clock skew in seconds.

    Returns:
        A configured ``AsyncJWTVerifier`` when ``build_auth_config(...)``
        yields a config; otherwise ``None``.

    Raises:
        Any exception raised by ``build_auth_config(...)`` or
        ``AsyncJWTVerifier(config=config)``.
    """
    config = build_auth_config(
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        clock_skew_seconds=clock_skew_seconds,
    )
    if config is None:
        return None
    return AsyncJWTVerifier(config=config)


def normalized_principal_claims(
    *,
    claims: Mapping[str, Any],
    invalid_token_error: InvalidTokenErrorFactory,
    subject_keys: Sequence[str] = ("sub",),
    scope_keys: Sequence[str] = ("scope_id",),
    tenant_keys: Sequence[str] = ("tenant_id", "org_id"),
    scopes_claim: str = "scope",
    permissions_claim: str = "permissions",
) -> NormalizedPrincipalClaims:
    """Normalize principal fields from a JWT or service-auth payload.

    Args:
        claims: JWT-like claim payload to normalize.
        invalid_token_error: Factory used to build token-validation exceptions.
        subject_keys: Claim keys to check for subject identity.
        scope_keys: Claim keys to check for explicit scope identifier.
        tenant_keys: Claim keys to check for tenant identifier.
        scopes_claim: Claim name containing scopes.
        permissions_claim: Claim name containing permissions.

    Returns:
        Normalized principal values suitable for authorization decisions.

    Raises:
        Exception: Built by ``invalid_token_error`` when required claims are
            missing or malformed.
    """
    subject = claim_as_str(claims=claims, keys=subject_keys)
    if subject is None:
        raise invalid_token_error("token subject claim is missing")

    tenant_id = claim_as_str(claims=claims, keys=tenant_keys)
    scope_id = (
        claim_as_str(claims=claims, keys=scope_keys) or tenant_id or subject
    )

    return NormalizedPrincipalClaims(
        subject=subject,
        scope_id=scope_id,
        tenant_id=tenant_id,
        scopes=tuple(
            collect_string_claim(
                claims.get(scopes_claim),
                invalid_token_error,
            )
        ),
        permissions=tuple(
            collect_string_claim(
                claims.get(permissions_claim),
                invalid_token_error,
            )
        ),
    )


def claim_as_str(
    *,
    claims: Mapping[str, Any],
    keys: Sequence[str],
) -> str | None:
    """Return the first non-blank claim string among the provided keys.

    Args:
        claims: JWT-like claim payload to inspect.
        keys: Candidate claim keys in lookup order.

    Returns:
        The first non-empty string claim value, or ``None`` when none exist.
    """
    for key in keys:
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def collect_string_claim(
    value: object,
    invalid_token_error: InvalidTokenErrorFactory,
) -> list[str]:
    """Normalize a string or list claim into a deduplicated ordered list.

    Args:
        value: Raw claim value (string, list/tuple of strings, or ``None``).
        invalid_token_error: Factory used to build token-validation exceptions.

    Returns:
        Normalized ordered list of unique non-empty claim values.

    Raises:
        Exception: Built by ``invalid_token_error`` when claim type is invalid.
    """
    if value is None:
        return []
    if isinstance(value, str):
        seen_tokens: set[str] = set()
        normalized_tokens: list[str] = []
        for segment in value.split(" "):
            token = segment.strip()
            if not token or token in seen_tokens:
                continue
            seen_tokens.add(token)
            normalized_tokens.append(token)
        return normalized_tokens
    if isinstance(value, (list, tuple)):
        seen_list_tokens: set[str] = set()
        normalized_list_tokens: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise invalid_token_error("token claim type is invalid")
            token = item.strip()
            if not token or token in seen_list_tokens:
                continue
            seen_list_tokens.add(token)
            normalized_list_tokens.append(token)
        return normalized_list_tokens
    raise invalid_token_error("token claim type is invalid")


def _normalized_optional_setting(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
