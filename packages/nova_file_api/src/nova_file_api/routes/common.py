"""Shared router helpers for canonical runtime endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Header, Path, Query

from nova_file_api.config import Settings
from nova_file_api.errors import invalid_request
from nova_file_api.models import ErrorEnvelope, ReadinessResponse

OpenApiResponse = dict[str, Any]
OpenApiResponses = dict[int | str, OpenApiResponse]

IdempotencyKeyHeader = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        description=(
            "Client-supplied idempotency key used to deduplicate supported "
            "mutation requests."
        ),
    ),
]
ExportIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=128,
        description="Identifier of the caller-owned export workflow resource.",
    ),
]
ExportsLimitQuery = Annotated[
    int,
    Query(
        ge=1,
        le=200,
        description=(
            "Maximum number of caller-owned export workflow resources to "
            "return, ordered newest first."
        ),
    ),
]


def _response(
    *,
    model: type[object],
    description: str,
) -> OpenApiResponse:
    return {"model": model, "description": description}


UNAUTHORIZED_AND_FORBIDDEN_RESPONSES: OpenApiResponses = {
    "401": _response(
        model=ErrorEnvelope,
        description="Unauthorized - Bearer token is missing or invalid.",
    ),
    "403": _response(
        model=ErrorEnvelope,
        description="Forbidden - Caller lacks required scope or permission.",
    ),
}
VALIDATION_ERROR_RESPONSE: OpenApiResponses = {
    "422": _response(
        model=ErrorEnvelope,
        description="Unprocessable Content - Request validation failed.",
    ),
}
COMMON_ERROR_RESPONSES: OpenApiResponses = {
    **UNAUTHORIZED_AND_FORBIDDEN_RESPONSES,
    **VALIDATION_ERROR_RESPONSE,
}
IDEMPOTENCY_CONFLICT_RESPONSE: OpenApiResponses = {
    "409": _response(
        model=ErrorEnvelope,
        description="Conflict - Idempotency request is already in progress.",
    )
}
IDEMPOTENCY_UNAVAILABLE_RESPONSE: OpenApiResponses = {
    "503": _response(
        model=ErrorEnvelope,
        description="Service Unavailable - Idempotency storage is unavailable.",
    )
}
EXPORT_MUTATION_UNAVAILABLE_RESPONSE: OpenApiResponses = {
    "503": _response(
        model=ErrorEnvelope,
        description=(
            "Service Unavailable - Queue publishing or idempotency storage "
            "is unavailable."
        ),
    )
}
READINESS_UNAVAILABLE_RESPONSE: OpenApiResponses = {
    "503": _response(
        model=ReadinessResponse,
        description="Service Unavailable - Readiness failed.",
    )
}


def validated_idempotency_key(
    *,
    settings: Settings,
    idempotency_key: str | None,
) -> str | None:
    """Validate the Idempotency-Key header for mutation routes.

    Args:
        settings: Runtime settings used to check feature enablement.
        idempotency_key: Raw ``Idempotency-Key`` header value.

    Returns:
        The normalized idempotency key when provided and enabled.

    Raises:
        FileTransferError: If ``idempotency_key`` is blank when idempotency is
            enabled.
    """
    if not settings.idempotency_enabled:
        return None
    if idempotency_key is None:
        return None
    if not idempotency_key.strip():
        raise invalid_request("invalid Idempotency-Key header")
    return idempotency_key.strip()
