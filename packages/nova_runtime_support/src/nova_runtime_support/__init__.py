"""Internal shared runtime helpers for Nova services."""

from nova_runtime_support.auth_claims import (
    NormalizedPrincipalClaims,
    build_jwt_verifier,
    normalized_principal_claims,
)
from nova_runtime_support.http import (
    bind_request_id,
    canonical_error_content,
    finalize_request_id,
    request_id_from_request,
    unbind_request_id,
)
from nova_runtime_support.logging import configure_structlog
from nova_runtime_support.openapi import (
    SDK_VISIBILITY_EXTENSION,
    SDK_VISIBILITY_INTERNAL,
    apply_operation_response_refs,
    ensure_error_response_component,
    install_openapi_customizer,
    mark_operation_sdk_visibility,
    prune_validation_error_schemas,
    replace_validation_error_responses,
)

__all__ = [
    "NormalizedPrincipalClaims",
    "SDK_VISIBILITY_EXTENSION",
    "SDK_VISIBILITY_INTERNAL",
    "apply_operation_response_refs",
    "bind_request_id",
    "build_jwt_verifier",
    "canonical_error_content",
    "configure_structlog",
    "ensure_error_response_component",
    "finalize_request_id",
    "install_openapi_customizer",
    "mark_operation_sdk_visibility",
    "normalized_principal_claims",
    "prune_validation_error_schemas",
    "replace_validation_error_responses",
    "request_id_from_request",
    "unbind_request_id",
]
