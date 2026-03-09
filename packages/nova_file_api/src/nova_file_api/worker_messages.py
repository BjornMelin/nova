"""Worker message parsing and normalization helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True, frozen=True)
class WorkerJobMessage:
    """Normalized queue payload consumed by the worker loop."""

    job_id: str
    job_type: str
    scope_id: str
    payload: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_body(cls, *, body: str) -> WorkerJobMessage:
        """Parse and validate one SQS message body payload."""
        raw = json.loads(body)
        if not isinstance(raw, dict):
            raise ValueError("message body must be an object")
        if {"status", "result", "error"} & raw.keys():
            raise ValueError(
                "message body must not contain result-update fields"
            )
        job_id = str(raw.get("job_id", "")).strip()
        if not job_id:
            raise ValueError("message body is missing job_id")
        job_type = str(raw.get("job_type", "")).strip()
        if not job_type:
            raise ValueError("message body is missing job_type")
        scope_id = str(raw.get("scope_id", "")).strip()
        if not scope_id:
            raise ValueError("message body is missing scope_id")
        payload = raw.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("message body payload must be an object")
        try:
            created_at = parse_iso8601(str(raw.get("created_at", "")).strip())
        except ValueError as exc:
            raise ValueError("message body created_at is invalid") from exc
        return cls(
            job_id=job_id,
            job_type=job_type,
            scope_id=scope_id,
            payload=payload,
            created_at=created_at,
        )


@dataclass(slots=True, frozen=True)
class TransferProcessPayload:
    """Payload required for the canonical transfer.process worker job."""

    bucket: str
    key: str
    filename: str
    size_bytes: int
    content_type: str | None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> TransferProcessPayload:
        """Parse and validate one transfer.process worker payload."""
        bucket = str(raw.get("bucket", "")).strip()
        if not bucket:
            raise ValueError("transfer.process payload is missing bucket")
        key = str(raw.get("key", "")).strip()
        if not key:
            raise ValueError("transfer.process payload is missing key")
        filename = str(raw.get("filename", "")).strip()
        if not filename:
            raise ValueError("transfer.process payload is missing filename")
        raw_size_bytes = raw.get("size_bytes")
        if not isinstance(raw_size_bytes, int) or raw_size_bytes <= 0:
            raise ValueError(
                "transfer.process payload size_bytes must be a positive integer"
            )
        raw_content_type = raw.get("content_type")
        if raw_content_type is None:
            content_type = None
        elif isinstance(raw_content_type, str):
            content_type = raw_content_type.strip() or None
        else:
            raise ValueError(
                "transfer.process payload content_type must be a string or null"
            )
        return cls(
            bucket=bucket,
            key=key,
            filename=filename,
            size_bytes=raw_size_bytes,
            content_type=content_type,
        )


def approximate_receive_count(*, message: dict[str, Any]) -> int | None:
    """Extract ApproximateReceiveCount from an SQS message envelope."""
    attributes = message.get("Attributes")
    if not isinstance(attributes, dict):
        return None
    raw = attributes.get("ApproximateReceiveCount")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def parse_iso8601(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and accept trailing Z."""
    if not value:
        raise ValueError("created_at is missing")
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)
