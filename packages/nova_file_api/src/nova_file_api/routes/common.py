"""Shared router helpers for canonical runtime endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any

from fastapi import Header, Query

from nova_file_api.config import Settings
from nova_file_api.errors import invalid_request
from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import ErrorEnvelope, ReadinessResponse

OpenApiResponse = dict[str, Any]
OpenApiResponses = Mapping[int | str, OpenApiResponse]
FastApiResponses = dict[int | str, dict[str, Any]]

IdempotencyKeyHeader = Annotated[
    str | None,
    Header(alias="Idempotency-Key"),
]
JobsLimitQuery = Annotated[int, Query(ge=1, le=200)]


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
JOB_MUTATION_UNAVAILABLE_RESPONSE: OpenApiResponses = {
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


def merge_openapi_responses(
    *response_sets: Mapping[int | str, OpenApiResponse],
) -> FastApiResponses:
    """Build a FastAPI-compatible responses mapping from reusable pieces."""
    merged: FastApiResponses = {}
    for response_set in response_sets:
        for status_code, resp in response_set.items():
            if status_code in merged:
                msg = (
                    f"OpenAPI responses conflict: status {status_code!r} is "
                    f"already defined when merging response metadata"
                )
                raise ValueError(msg)
            merged[status_code] = dict(resp)
    return merged


def emit_request_metric(
    *,
    metrics: MetricsCollector,
    route: str,
    status: str,
) -> None:
    """Emit a low-cardinality request counter.

    Args:
        metrics: Metrics collector used for EMF output.
        route: Route name used for metric dimensions.
        status: Request outcome label.
    """
    metrics.emit_emf(
        metric_name="requests_total",
        value=1,
        unit="Count",
        dimensions={"route": route, "status": status},
    )


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
