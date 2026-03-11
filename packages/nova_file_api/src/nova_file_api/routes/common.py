"""Shared router helpers for canonical runtime endpoints."""

from __future__ import annotations

from hmac import compare_digest
from typing import Annotated

import structlog
from fastapi import Header, Query

from nova_file_api.config import Settings
from nova_file_api.errors import forbidden, invalid_request
from nova_file_api.metrics import MetricsCollector

WORKER_TOKEN_NOT_CONFIGURED = "worker update token not configured"
IdempotencyKeyHeader = Annotated[
    str | None,
    Header(alias="Idempotency-Key"),
]
WorkerTokenHeader = Annotated[
    str | None,
    Header(alias="X-Worker-Token"),
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
    """
    if not settings.idempotency_enabled:
        return None
    if idempotency_key is None:
        return None
    if not idempotency_key.strip():
        raise invalid_request("invalid Idempotency-Key header")
    return idempotency_key.strip()


def validate_worker_update_token(
    *,
    settings: Settings,
    worker_token: str | None,
) -> None:
    """Validate the worker-side update token.

    Args:
        settings: Runtime settings containing worker-token configuration.
        worker_token: Raw ``X-Worker-Token`` header value.
    """
    expected = settings.jobs_worker_update_token
    expected_token = (
        expected.get_secret_value() if expected is not None else None
    )
    if expected_token is None or not expected_token.strip():
        is_prod = settings.environment.lower() in {"prod", "production"}
        if is_prod or not (
            settings.jobs_allow_insecure_missing_worker_token_nonprod
        ):
            raise forbidden(WORKER_TOKEN_NOT_CONFIGURED)
        structlog.get_logger("api").warning(
            "worker_update_token_validation_skipped",
            environment=settings.environment,
        )
        return

    provided = worker_token.strip() if worker_token else ""
    if not compare_digest(expected_token.strip(), provided):
        raise forbidden("invalid worker update token")
