"""Request-level metric helpers shared across API layers."""

from __future__ import annotations

from nova_runtime_support.metrics import MetricsCollector


def emit_request_metric(
    *,
    metrics: MetricsCollector,
    route: str,
    status: str,
) -> None:
    """Emit a low-cardinality request counter.

    Args:
        metrics: Metrics collector that receives the EMF payload.
        route: Route name recorded on the request metric dimensions.
        status: Request outcome recorded on the request metric dimensions.

    Returns:
        None: This helper returns no value.
    """
    metrics.emit_emf(
        metric_name="requests_total",
        value=1,
        unit="Count",
        dimensions={"route": route, "status": status},
    )
