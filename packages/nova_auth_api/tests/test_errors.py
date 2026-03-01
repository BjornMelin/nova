from __future__ import annotations

import pytest
from nova_auth_api.errors import from_oidc_auth_error
from oidc_jwt_verifier import AuthError


@pytest.mark.parametrize(
    "code",
    [
        "invalid_issuer",
        "invalid_audience",
        "token_expired",
        "token_not_yet_valid",
    ],
)
def test_from_oidc_auth_error_maps_jwt_claim_failures(code: str) -> None:
    mapped = from_oidc_auth_error(
        AuthError(code=code, message="claim rejected", status_code=401)
    )

    assert mapped.code == code
    assert mapped.status_code == 401
    header = mapped.headers.get("WWW-Authenticate", "")
    assert header.startswith("Bearer ")
    assert 'error="invalid_token"' in header


def test_from_oidc_auth_error_maps_insufficient_scope_with_rfc6750_header() -> (
    None
):
    mapped = from_oidc_auth_error(
        AuthError(
            code="insufficient_scope",
            message="missing required scopes",
            status_code=403,
            required_scopes=("uploads:write",),
        )
    )

    assert mapped.code == "insufficient_scope"
    assert mapped.status_code == 403
    header = mapped.headers.get("WWW-Authenticate", "")
    assert 'error="insufficient_scope"' in header
    assert "uploads:write" in header
