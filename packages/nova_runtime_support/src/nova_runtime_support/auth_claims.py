"""Shared JWT verifier and principal-claim normalization helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from oidc_jwt_verifier import AuthConfig, JWTVerifier


@dataclass(frozen=True, slots=True)
class NormalizedPrincipalClaims:
    """Normalized principal fields extracted from a JWT-like payload."""

    subject: str
    scope_id: str
    tenant_id: str | None
    scopes: tuple[str, ...]
    permissions: tuple[str, ...]


InvalidTokenErrorFactory = Callable[[str], Exception]


def build_jwt_verifier(
    *,
    issuer: str | None,
    audience: str | None,
    jwks_url: str | None,
    clock_skew_seconds: int,
    required_scopes: Sequence[str] = (),
    required_permissions: Sequence[str] = (),
) -> JWTVerifier | None:
    """Build a JWT verifier when the required OIDC settings are present."""
    issuer = _normalized_optional_setting(issuer)
    audience = _normalized_optional_setting(audience)
    jwks_url = _normalized_optional_setting(jwks_url)
    if issuer is None or audience is None or jwks_url is None:
        return None
    config = AuthConfig(
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        required_scopes=tuple(required_scopes),
        required_permissions=tuple(required_permissions),
        leeway_s=clock_skew_seconds,
    )
    return JWTVerifier(config=config)


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
    """Normalize principal fields from a JWT or service-auth payload."""
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
    """Return the first non-blank string claim value among the provided keys."""
    for key in keys:
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def collect_string_claim(
    value: object,
    invalid_token_error: InvalidTokenErrorFactory,
) -> list[str]:
    """Normalize a string/list claim into a deduplicated ordered list."""
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
