"""Metrics collector emission and payload-shape tests."""

from __future__ import annotations

from typing import Any

from nova_file_api.metrics import MetricsCollector


def test_emit_emf_writes_valid_payload_with_bounded_dimensions() -> None:
    """EMF logger output should include valid CloudWatch metric metadata."""
    metrics = MetricsCollector(namespace="Tests")
    captured: dict[str, Any] = {}

    def _capture(event: str, **kwargs: object) -> None:
        captured["event"] = event
        captured["kwargs"] = kwargs

    metrics._logger.info = _capture

    metrics.emit_emf(
        metric_name="requests_total",
        value=1.0,
        unit="Count",
        dimensions={"route": "jobs_enqueue", "status": "ok"},
    )

    assert captured["event"] == "emf_metric"
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert "emf" not in kwargs
    assert kwargs["requests_total"] == 1.0
    assert kwargs["route"] == "jobs_enqueue"
    assert kwargs["status"] == "ok"
    aws_meta = kwargs["_aws"]["CloudWatchMetrics"][0]
    assert aws_meta["Namespace"] == "Tests"
    assert aws_meta["Dimensions"] == [["route", "status"]]
    assert aws_meta["Metrics"] == [{"Name": "requests_total", "Unit": "Count"}]
