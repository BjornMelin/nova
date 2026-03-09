"""Worker callback retry and result-serialization helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nova_file_api.transfer import ExportCopyResult


@dataclass(slots=True)
class WorkerResultUpdateError(Exception):
    """Raised when a worker result callback is not durably accepted."""

    message: str
    retryable: bool
    status_code: int | None = None
    error_type: str | None = None

    def __post_init__(self) -> None:
        """Provide a stable exception message for logging surfaces."""
        Exception.__init__(self, self.message)


def result_update_retry_delay_seconds(
    *,
    attempt: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    random_uniform: Callable[[float, float], float],
) -> float:
    """Return exponential-backoff delay with jitter for callback retries."""
    delay_seconds = float(
        min(base_delay_seconds * (2 ** (attempt - 1)), max_delay_seconds)
    )
    jitter = random_uniform(0.75, 1.25)
    return float(delay_seconds * jitter)


def success_result_from_export(*, export: ExportCopyResult) -> dict[str, Any]:
    """Return the canonical worker success result payload."""
    return {
        "export_key": export.export_key,
        "download_filename": export.download_filename,
    }
