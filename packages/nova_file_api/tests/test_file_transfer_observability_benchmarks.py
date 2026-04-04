"""Regression coverage for transfer benchmark helper math."""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.perf.file_transfer_observability_baseline import (
    CURRENT_MAX_CONCURRENCY,
    CURRENT_PART_SIZE_BYTES,
    build_browser_multipart_plan,
    gibibytes,
    summarize_latency,
)


def test_browser_plan_matches_current_500_gib_defaults() -> None:
    """The benchmark helper should mirror the current browser batching rule."""
    plan = build_browser_multipart_plan(
        file_size_bytes=gibibytes(500),
        part_size_bytes=CURRENT_PART_SIZE_BYTES,
        max_concurrency=CURRENT_MAX_CONCURRENCY,
    )

    assert plan.sign_batch_size == 64
    assert plan.total_parts == 4000
    assert plan.sign_requests == 63


def test_summarize_latency_is_repeatable() -> None:
    """Latency summaries should stay deterministic for fixed samples."""
    summary = summarize_latency(
        samples_ms=[10.0, 20.0, 30.0, 40.0],
        iterations=4,
    )

    assert summary == {
        "avg_ms": 25.0,
        "max_ms": 40.0,
        "min_ms": 10.0,
        "p50_ms": 25.0,
        "p95_ms": 38.5,
        "p99_ms": 39.7,
    }
