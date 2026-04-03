"""Shared helpers for transfer and export benchmark scripts."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Final

CURRENT_MULTIPART_THRESHOLD_BYTES: Final[int] = 100 * 1024 * 1024
CURRENT_PART_SIZE_BYTES: Final[int] = 128 * 1024 * 1024
CURRENT_MAX_CONCURRENCY: Final[int] = 4
CURRENT_MAX_UPLOAD_BYTES: Final[int] = 500 * 1024 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class BrowserMultipartPlan:
    """Describe the current browser helper batching plan for one upload."""

    file_size_bytes: int
    part_size_bytes: int
    max_concurrency: int
    sign_batch_size: int
    total_parts: int
    sign_requests: int


def gibibytes(value: float) -> int:
    """Convert GiB into bytes using binary units."""
    return int(value * 1024 * 1024 * 1024)


def parse_sizes_gib(raw: str) -> list[int]:
    """Parse a comma-separated GiB list and reject empty or invalid entries."""
    values = [item.strip() for item in raw.split(",")]
    if not values or any(not item for item in values):
        raise ValueError(
            "sizes_gib must contain comma-separated numeric values"
        )
    parsed: list[int] = []
    for item in values:
        try:
            parsed.append(gibibytes(float(item)))
        except ValueError as exc:
            raise ValueError(f"invalid GiB value: {item}") from exc
    return parsed


def multipart_part_count(*, file_size_bytes: int, part_size_bytes: int) -> int:
    """Return the number of multipart parts needed for one file size."""
    if file_size_bytes <= 0:
        raise ValueError("file_size_bytes must be > 0")
    if part_size_bytes <= 0:
        raise ValueError("part_size_bytes must be > 0")
    return math.ceil(file_size_bytes / part_size_bytes)


def browser_sign_batch_size(
    *,
    max_concurrency: int,
    configured_sign_batch_size: int | None = None,
) -> int:
    """Mirror the current `file_transfer.js` default batching rule."""
    if max_concurrency <= 0:
        raise ValueError("max_concurrency must be > 0")
    cap = min(16, max_concurrency * 2)
    if (
        configured_sign_batch_size is not None
        and configured_sign_batch_size <= 0
    ):
        raise ValueError("configured_sign_batch_size must be > 0")
    if configured_sign_batch_size is not None:
        if configured_sign_batch_size > cap:
            raise ValueError(f"configured_sign_batch_size must be <= {cap}")
        return configured_sign_batch_size
    return min(16, max(1, max_concurrency * 2))


def sign_request_count(*, total_parts: int, sign_batch_size: int) -> int:
    """Return the number of control-plane sign requests for one upload."""
    if total_parts <= 0:
        raise ValueError("total_parts must be > 0")
    if sign_batch_size <= 0:
        raise ValueError("sign_batch_size must be > 0")
    return math.ceil(total_parts / sign_batch_size)


def build_browser_multipart_plan(
    *,
    file_size_bytes: int,
    part_size_bytes: int = CURRENT_PART_SIZE_BYTES,
    max_concurrency: int = CURRENT_MAX_CONCURRENCY,
    configured_sign_batch_size: int | None = None,
) -> BrowserMultipartPlan:
    """Build the current browser multipart plan for one upload scenario."""
    batch_size = browser_sign_batch_size(
        max_concurrency=max_concurrency,
        configured_sign_batch_size=configured_sign_batch_size,
    )
    total_parts = multipart_part_count(
        file_size_bytes=file_size_bytes,
        part_size_bytes=part_size_bytes,
    )
    return BrowserMultipartPlan(
        file_size_bytes=file_size_bytes,
        part_size_bytes=part_size_bytes,
        max_concurrency=max_concurrency,
        sign_batch_size=batch_size,
        total_parts=total_parts,
        sign_requests=sign_request_count(
            total_parts=total_parts,
            sign_batch_size=batch_size,
        ),
    )


def percentile(samples_ms: list[float], percentile_value: float) -> float:
    """Return one percentile from a sorted latency list."""
    if not samples_ms:
        raise ValueError("samples_ms must not be empty")
    if percentile_value < 0 or percentile_value > 100:
        raise ValueError("percentile_value must be between 0 and 100")
    ordered = sorted(samples_ms)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (percentile_value / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * weight)


def summarize_latency(
    *,
    samples_ms: list[float],
    iterations: int,
) -> dict[str, float]:
    """Return a stable summary for one benchmark sample set."""
    if iterations <= 0:
        raise ValueError("iterations must be > 0")
    if len(samples_ms) != iterations:
        raise ValueError("samples_ms length must match iterations")
    return {
        "avg_ms": round(statistics.fmean(samples_ms), 3),
        "p50_ms": round(percentile(samples_ms, 50), 3),
        "p95_ms": round(percentile(samples_ms, 95), 3),
        "p99_ms": round(percentile(samples_ms, 99), 3),
        "min_ms": round(min(samples_ms), 3),
        "max_ms": round(max(samples_ms), 3),
    }


def bytes_text(value: int) -> str:
    """Return a stable human-readable binary byte label."""
    if value < 0:
        raise ValueError("value must be >= 0")
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    size = float(value)
    unit = units[0]
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            break
        size /= 1024.0
    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.2f} {unit}"
