"""Stable OpenAPI operation identifiers for nova-auth-api."""

from __future__ import annotations

from typing import Final

HEALTH_LIVE_OPERATION_ID: Final = "health_live"
HEALTH_READY_OPERATION_ID: Final = "health_ready"
VERIFY_TOKEN_OPERATION_ID: Final = "verify_token"
INTROSPECT_TOKEN_OPERATION_ID: Final = "introspect_token"

OPERATION_ID_BY_PATH_AND_METHOD: Final[dict[str, dict[str, str]]] = {
    "/v1/health/live": {"get": HEALTH_LIVE_OPERATION_ID},
    "/v1/health/ready": {"get": HEALTH_READY_OPERATION_ID},
    "/v1/token/verify": {"post": VERIFY_TOKEN_OPERATION_ID},
    "/v1/token/introspect": {"post": INTROSPECT_TOKEN_OPERATION_ID},
}
