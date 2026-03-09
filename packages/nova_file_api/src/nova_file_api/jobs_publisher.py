"""Async job queue publisher backends."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from nova_file_api.metrics import MetricsCollector
from nova_file_api.models import JobRecord, JobStatus

from .jobs_repository import JobRepository


class JobPublisher(Protocol):
    """Queue interface for background job dispatch."""

    def publish(self, *, job: JobRecord) -> None:
        """Publish job record to background queue."""

    def post_publish(
        self,
        *,
        job: JobRecord,
        repository: JobRepository,
        metrics: MetricsCollector,
    ) -> None:
        """Run optional post-publish handling."""

    def healthcheck(self) -> bool:
        """Return readiness of the backing queue dependency."""


@dataclass(slots=True)
class JobPublishError(Exception):
    """Raised when queue publish fails and enqueue cannot proceed."""

    details: dict[str, Any]

    def __post_init__(self) -> None:
        """Provide a stable exception message for logging surfaces."""
        Exception.__init__(self, "queue publish failed")


@dataclass(slots=True)
class MemoryJobPublisher:
    """In-memory queue that can process jobs immediately."""

    process_immediately: bool = True

    def publish(self, *, job: JobRecord) -> None:
        """Publish a memory-backed job with no external queue side effect."""
        del job
        return

    def post_publish(
        self,
        *,
        job: JobRecord,
        repository: JobRepository,
        metrics: MetricsCollector,
    ) -> None:
        """Simulate immediate worker completion for memory-backed jobs."""
        if not self.process_immediately:
            return
        running = job.model_copy(
            update={"status": JobStatus.RUNNING, "updated_at": _utc_now()}
        )
        repository.update(running)
        done = running.model_copy(
            update={
                "status": JobStatus.SUCCEEDED,
                "result": {"accepted": True, "mode": "memory"},
                "updated_at": _utc_now(),
            }
        )
        repository.update(done)
        metrics.incr("jobs_succeeded")

    def healthcheck(self) -> bool:
        """Return readiness for the memory-backed publisher."""
        return True


@dataclass(slots=True)
class SqsJobPublisher:
    """SQS-backed queue publisher."""

    queue_url: str
    retry_mode: str = "standard"
    retry_total_max_attempts: int = 3
    _sqs: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Create the SQS client after dataclass construction."""
        self._sqs = boto3.client(
            "sqs",
            config=Config(
                retries={
                    "mode": self.retry_mode,
                    "total_max_attempts": self.retry_total_max_attempts,
                }
            ),
        )

    def publish(self, *, job: JobRecord) -> None:
        """Publish one job payload to SQS."""
        payload = {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "scope_id": job.scope_id,
            "payload": job.payload,
            "created_at": job.created_at.isoformat(),
        }
        try:
            self._sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(
                    payload, separators=(",", ":"), sort_keys=True
                ),
            )
        except ClientError as exc:
            raise JobPublishError(
                details={
                    "error_type": "ClientError",
                    "error_code": str(
                        exc.response.get("Error", {}).get("Code", "Unknown")
                    ),
                }
            ) from exc
        except BotoCoreError as exc:
            raise JobPublishError(
                details={
                    "error_type": type(exc).__name__,
                    "error_code": "BotoCoreError",
                }
            ) from exc

    def post_publish(
        self,
        *,
        job: JobRecord,
        repository: JobRepository,
        metrics: MetricsCollector,
    ) -> None:
        """Skip local follow-up because SQS mode is handled asynchronously."""
        del job, repository, metrics
        return

    def healthcheck(self) -> bool:
        """Return whether queue metadata can be fetched successfully."""
        try:
            self._sqs.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=["QueueArn"],
            )
        except (ClientError, BotoCoreError):
            return False
        return True


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)
