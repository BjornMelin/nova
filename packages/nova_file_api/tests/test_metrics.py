"""Metrics collector emission and payload-shape tests."""

from __future__ import annotations

from typing import Any, cast

from nova_file_api.metrics import MetricsCollector


def test_emit_emf_writes_valid_payload_with_bounded_dimensions() -> None:
    """EMF logger output should include valid CloudWatch metric metadata."""
    metrics = MetricsCollector(namespace="Tests")
    captured: dict[str, object] = {}

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
    kwargs_obj = captured["kwargs"]
    assert isinstance(kwargs_obj, dict)
    kwargs = cast("dict[str, Any]", kwargs_obj)
    assert "emf" not in kwargs_obj
    assert kwargs["requests_total"] == 1.0
    assert kwargs["route"] == "jobs_enqueue"
    assert kwargs["status"] == "ok"

    aws_obj = kwargs.get("_aws")
    assert isinstance(aws_obj, dict)
    cloudwatch_metrics = aws_obj.get("CloudWatchMetrics")
    assert isinstance(cloudwatch_metrics, list)
    assert cloudwatch_metrics
    first_metric = cloudwatch_metrics[0]
    assert isinstance(first_metric, dict)

    assert first_metric["Namespace"] == "Tests"
    assert first_metric["Dimensions"] == [["route", "status"]]
    assert first_metric["Metrics"] == [
        {"Name": "requests_total", "Unit": "Count"}
    ]
