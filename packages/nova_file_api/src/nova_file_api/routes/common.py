"""Shared router helpers for canonical runtime endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, Query

from nova_file_api.config import Settings
from nova_file_api.errors import invalid_request
from nova_file_api.metrics import MetricsCollector

IdempotencyKeyHeader = Annotated[
    str | None,
    Header(alias="Idempotency-Key"),
]
JobsLimitQuery = Annotated[int, Query(ge=1, le=200)]


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
