"""Shared router helpers for canonical runtime endpoints."""

from __future__ import annotations

from hmac import compare_digest
from typing import Annotated

import structlog
from fastapi import Header, Query

from nova_file_api.container import AppContainer
from nova_file_api.errors import forbidden, invalid_request

WORKER_TOKEN_NOT_CONFIGURED = "worker update token not configured"  # noqa: S105
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
    container: AppContainer,
    route: str,
    status: str,
) -> None:
    """Emit a low-cardinality request counter.

    Args:
        container (AppContainer): Application dependency container.
        route (str): Route name used for metric dimensions.
        status (str): Request outcome label.

    Returns:
        None: Function returns ``None`` after emitting the metric.
    """
    container.metrics.emit_emf(
        metric_name="requests_total",
        value=1,
        unit="Count",
        dimensions={"route": route, "status": status},
    )


def validated_idempotency_key(
    *,
    container: AppContainer,
    idempotency_key: str | None,
) -> str | None:
    """Validate the Idempotency-Key header for mutation routes.

    Args:
        container: Application dependency container.
        idempotency_key: Raw ``Idempotency-Key`` header value.

    Returns:
        The normalized idempotency key when provided and enabled; otherwise
        ``None``.

    Raises:
        FileTransferError: If the header is present but blank.
    """
    if not container.settings.idempotency_enabled:
        return None
    if idempotency_key is None:
        return None
    if not idempotency_key.strip():
        raise invalid_request("invalid Idempotency-Key header")
    return idempotency_key.strip()


def validate_worker_update_token(
    *,
    container: AppContainer,
    worker_token: str | None,
) -> None:
    """Validate the worker-side update token.

    Args:
        container: Application dependency container.
        worker_token: Raw ``X-Worker-Token`` header value.

    Returns:
        None.

    Raises:
        FileTransferError: If the worker token is missing/invalid when
            enforcement is required.
    """
    expected = container.settings.jobs_worker_update_token
    expected_token = (
        expected.get_secret_value() if expected is not None else None
    )
    if expected_token is None or not expected_token.strip():
        is_prod = container.settings.environment.lower() in {
            "prod",
            "production",
        }
        if is_prod or not (
            container.settings.jobs_allow_insecure_missing_worker_token_nonprod
        ):
            raise forbidden(WORKER_TOKEN_NOT_CONFIGURED)
        structlog.get_logger("api").warning(
            "worker_update_token_validation_skipped",
            environment=container.settings.environment,
        )
        return

    provided = worker_token.strip() if worker_token else ""
    if not compare_digest(expected_token.strip(), provided):
        raise forbidden("invalid worker update token")
