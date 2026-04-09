"""Shared assertion helpers for runtime release validation."""

from __future__ import annotations

import json

from scripts.release.validate_runtime_release_types import AssertionCheck


def stringify_value(value: object) -> str:
    """Return a stable string representation for one assertion value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str) and value == "":
        return "<empty>"
    if isinstance(value, (int, float, str)):
        return str(value)
    return json.dumps(value, sort_keys=True)


def record_assertion(
    *,
    checks: list[AssertionCheck],
    failures: list[str],
    name: str,
    expected: str,
    actual: object,
    ok: bool,
    failure_message: str | None = None,
) -> None:
    """Record one structured assertion and append a failure when it fails."""
    checks.append(
        AssertionCheck(
            name=name,
            expected=expected,
            actual=stringify_value(actual),
            ok=ok,
        )
    )
    if ok:
        return
    failures.append(
        failure_message
        or f"{name} expected {expected}, got {stringify_value(actual)}"
    )
