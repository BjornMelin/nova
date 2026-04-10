"""Queue builders for runtime workflow worker lanes."""

from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import Duration, aws_sqs as sqs
from constructs import Construct

from .runtime_naming import (
    export_copy_worker_dlq_name,
    export_copy_worker_queue_name,
)
from .runtime_release_manifest import (
    FILE_TRANSFER_EXPORT_COPY_WORKER_ATTEMPTS,
    FILE_TRANSFER_EXPORT_COPY_WORKER_LEASE_SECONDS,
)


@dataclass(frozen=True)
class ExportCopyQueues:
    """Queues used by the SQS-backed export copy worker lane."""

    dlq: sqs.Queue
    max_concurrency: int
    queue: sqs.Queue


def create_export_copy_queues(
    scope: Construct,
    *,
    deployment_environment: str,
    max_concurrency: int,
) -> ExportCopyQueues:
    """Create the export-copy worker queue and DLQ."""
    dlq = sqs.Queue(
        scope,
        "ExportCopyWorkerDlq",
        queue_name=export_copy_worker_dlq_name(deployment_environment),
        retention_period=Duration.days(14),
        encryption=sqs.QueueEncryption.SQS_MANAGED,
        enforce_ssl=True,
    )
    queue = sqs.Queue(
        scope,
        "ExportCopyWorkerQueue",
        queue_name=export_copy_worker_queue_name(deployment_environment),
        dead_letter_queue=sqs.DeadLetterQueue(
            queue=dlq,
            max_receive_count=FILE_TRANSFER_EXPORT_COPY_WORKER_ATTEMPTS,
        ),
        encryption=sqs.QueueEncryption.SQS_MANAGED,
        enforce_ssl=True,
        receive_message_wait_time=Duration.seconds(20),
        visibility_timeout=Duration.seconds(
            FILE_TRANSFER_EXPORT_COPY_WORKER_LEASE_SECONDS
        ),
    )
    return ExportCopyQueues(
        dlq=dlq,
        max_concurrency=max_concurrency,
        queue=queue,
    )
