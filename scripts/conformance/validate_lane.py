"""Validate Nova v1 conformance fixtures for Dash/Shiny/TypeScript lanes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FIXTURE_ROOT = Path("packages/contracts/fixtures/v1")


class ConformanceError(RuntimeError):
    """Raised when a conformance invariant fails."""


def _read_json(relative_path: str) -> dict[str, Any]:
    fixture_path = FIXTURE_ROOT / relative_path
    try:
        fixture_text = fixture_path.read_text(encoding="utf-8")
        payload = json.loads(fixture_text)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise ConformanceError(
            f"fixture must decode to an object: {fixture_path} - {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ConformanceError(
            f"fixture must decode to an object: {fixture_path}"
        )
    return payload


def _assert_error_envelope(payload: dict[str, Any], *, code: str) -> None:
    error = payload.get("error")
    if not isinstance(error, dict):
        raise ConformanceError("error envelope is missing")
    for key in ("code", "message", "request_id"):
        if not isinstance(error.get(key), str) or not error[key]:
            raise ConformanceError(f"error envelope missing non-empty '{key}'")
    if error["code"] != code:
        actual_code = error["code"]
        raise ConformanceError(
            f"error.code expected '{code}', got '{actual_code}'"
        )


def _validate_manifest_and_fixtures() -> dict[str, Any]:
    manifest = _read_json("manifest.json")

    for group in ("schemas", "fixtures"):
        if group not in manifest:
            raise ConformanceError(f"manifest missing '{group}'")

    for schema_path in manifest["schemas"].values():
        if not (FIXTURE_ROOT / schema_path).is_file():
            raise ConformanceError(f"missing schema file: {schema_path}")

    for domain in manifest["fixtures"].values():
        for fixture_path in domain.values():
            if not (FIXTURE_ROOT / fixture_path).is_file():
                raise ConformanceError(f"missing fixture file: {fixture_path}")

    return manifest


def validate_lane(lane: str) -> None:
    """Validate fixture invariants for the requested conformance lane."""
    manifest = _validate_manifest_and_fixtures()

    auth = manifest["fixtures"]["auth"]
    jobs = manifest["fixtures"]["jobs"]
    transfer = manifest["fixtures"]["transfer"]

    verify_success = _read_json(auth["verify_success"])
    verify_401 = _read_json(auth["verify_401_invalid_token"])
    verify_403 = _read_json(auth["verify_403_insufficient_scope"])
    enqueue_503 = _read_json(jobs["enqueue_503_queue_unavailable"])
    transfer_request = _read_json(transfer["initiate_request"])

    principal = verify_success.get("principal")
    if not isinstance(principal, dict) or not isinstance(
        principal.get("subject"), str
    ):
        raise ConformanceError("verify success principal shape is invalid")

    _assert_error_envelope(verify_401, code="invalid_token")
    _assert_error_envelope(verify_403, code="insufficient_scope")
    _assert_error_envelope(enqueue_503, code="queue_unavailable")

    if not isinstance(transfer_request.get("session_id"), str):
        raise ConformanceError("transfer initiate request missing session_id")

    if lane not in {"dash", "shiny", "typescript"}:
        raise ConformanceError(f"unsupported lane: {lane}")


def main() -> int:
    """CLI entrypoint for lane-specific conformance validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lane",
        choices=["dash", "shiny", "typescript"],
        required=True,
    )
    args = parser.parse_args()

    validate_lane(args.lane)
    print(f"v1 conformance lane passed: {args.lane}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
