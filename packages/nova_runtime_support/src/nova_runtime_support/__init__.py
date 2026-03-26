"""Internal shared runtime helpers for Nova services."""

from nova_runtime_support.auth_claims import (
    NormalizedPrincipalClaims,
    build_async_jwt_verifier,
    build_auth_config,
    normalized_principal_claims,
)
from nova_runtime_support.http import (
    CanonicalErrorSpec,
    RequestContextASGIMiddleware,
    RequestContextFastAPI,
    canonical_error_content,
    canonical_error_spec_from_error,
    register_fastapi_exception_handlers,
    request_id_from_request,
)
from nova_runtime_support.logging import configure_structlog
from nova_runtime_support.openapi import (
    SDK_VISIBILITY_EXTENSION,
    SDK_VISIBILITY_INTERNAL,
)

__all__ = [
    "SDK_VISIBILITY_EXTENSION",
    "SDK_VISIBILITY_INTERNAL",
    "CanonicalErrorSpec",
    "NormalizedPrincipalClaims",
    "RequestContextASGIMiddleware",
    "RequestContextFastAPI",
    "build_async_jwt_verifier",
    "build_auth_config",
    "canonical_error_content",
    "canonical_error_spec_from_error",
    "configure_structlog",
    "normalized_principal_claims",
    "register_fastapi_exception_handlers",
    "request_id_from_request",
]
