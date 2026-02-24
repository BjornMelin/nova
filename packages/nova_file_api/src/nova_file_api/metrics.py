"""Metrics collection and EMF emission helpers."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog


@dataclass(slots=True)
class LatencyStat:
    """Aggregated latency stats in milliseconds."""

    total_ms: float = 0.0
    count: int = 0

    def observe(self, value_ms: float) -> None:
        """Record a latency observation."""
        self.total_ms += value_ms
        self.count += 1

    @property
    def avg_ms(self) -> float:
        """Return average milliseconds or zero when empty."""
        if self.count == 0:
            return 0.0
        return self.total_ms / self.count


class MetricsCollector:
    """Simple in-process metrics collector with EMF logging."""

    def __init__(self, *, namespace: str) -> None:
        """Initialize metrics collector state.

        Args:
            namespace: CloudWatch metric namespace for EMF payloads.
        """
        self._namespace = namespace
        self._counters: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, LatencyStat] = defaultdict(LatencyStat)
        self._logger = structlog.get_logger("metrics")

    def incr(self, key: str, value: int = 1) -> None:
        """Increment counter by value."""
        self._counters[key] += value

    def observe_ms(self, key: str, value_ms: float) -> None:
        """Record latency metric in milliseconds."""
        self._latencies[key].observe(value_ms)

    @contextmanager
    def timed(self, key: str) -> Iterator[None]:
        """Context manager that records elapsed time under key."""
        started = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self.observe_ms(key, elapsed_ms)

    def emit_emf(
        self,
        *,
        metric_name: str,
        value: float,
        unit: str,
        dimensions: dict[str, str],
    ) -> None:
        """Emit CloudWatch Embedded Metric Format via structured logs."""
        payload: dict[str, Any] = {
            "_aws": {
                "Timestamp": int(datetime.now(tz=UTC).timestamp() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": self._namespace,
                        "Dimensions": [sorted(dimensions.keys())],
                        "Metrics": [{"Name": metric_name, "Unit": unit}],
                    }
                ],
            },
            metric_name: value,
            **dimensions,
        }
        self._logger.info("emf_metric", **payload)

    def counters_snapshot(self) -> dict[str, int]:
        """Return immutable snapshot of counters."""
        return dict(self._counters)

    def latency_snapshot(self) -> dict[str, float]:
        """Return average latency snapshot in milliseconds."""
        return {
            key: round(stat.avg_ms, 3)
            for key, stat in self._latencies.items()
            if stat.count > 0
        }
