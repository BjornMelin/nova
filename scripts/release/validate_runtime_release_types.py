"""Shared data types for runtime release validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteCheck:
    """Route validation result for one HTTP request."""

    kind: str
    method: str
    path: str
    expected: str
    status_code: int
    ok: bool


@dataclass(frozen=True)
class ConcurrencyCheck:
    """Reserved-concurrency validation result for one Lambda function."""

    function_group: str
    function_logical_id: str
    function_name: str
    expected_reserved_concurrency: int | None
    actual_reserved_concurrency: int | None
    ok: bool


@dataclass(frozen=True)
class AssertionCheck:
    """Structured validation assertion for capability and AWS checks."""

    name: str
    expected: str
    actual: str
    ok: bool


@dataclass(frozen=True)
class RequestResult:
    """HTTP response data used by runtime validation checks."""

    status_code: int | None
    headers: dict[str, str]
    body: bytes | None
    error: str | None
