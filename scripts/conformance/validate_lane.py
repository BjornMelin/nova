"""Validate Nova v1 conformance fixtures for Dash/Shiny/TypeScript lanes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from nova_file_api.models import (
    CapabilitiesResponse,
    CreateExportRequest,
    ErrorEnvelope,
    ExportListResponse,
    ExportResource,
    InitiateUploadRequest,
    InitiateUploadResponse,
    ReleaseInfoResponse,
    ResourcePlanResponse,
)

FIXTURE_ROOT = Path("packages/contracts/fixtures/v1")


class ConformanceError(RuntimeError):
    """Raised when a conformance invariant fails."""


def _read_json(relative_path: str) -> dict[str, Any]:
    fixture_path = FIXTURE_ROOT / relative_path
    try:
        fixture_text = fixture_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConformanceError(
            f"fixture could not be read: {fixture_path} - {exc}"
        ) from exc
    try:
        payload = json.loads(fixture_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ConformanceError(
            f"fixture must be valid JSON: {fixture_path} - {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ConformanceError(
            f"fixture must decode to an object: {fixture_path}"
        )
    return payload


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

    transfer = manifest["fixtures"]["transfer"]
    exports = manifest["fixtures"]["exports"]
    v1api = manifest["fixtures"]["v1api"]

    InitiateUploadRequest.model_validate(
        _read_json(transfer["initiate_request"])
    )
    InitiateUploadResponse.model_validate(
        _read_json(transfer["initiate_success"])
    )
    CreateExportRequest.model_validate(_read_json(exports["create_request"]))
    ExportResource.model_validate(_read_json(exports["create_success"]))
    ExportResource.model_validate(_read_json(exports["get_success"]))
    ExportListResponse.model_validate(_read_json(exports["list_success"]))
    ExportResource.model_validate(_read_json(exports["cancel_success"]))
    ErrorEnvelope.model_validate(
        _read_json(exports["create_503_queue_unavailable"])
    )
    CapabilitiesResponse.model_validate(
        _read_json(v1api["capabilities_success"])
    )
    ResourcePlanResponse.model_validate(
        _read_json(v1api["resources_plan_success"])
    )
    ReleaseInfoResponse.model_validate(
        _read_json(v1api["releases_info_success"])
    )

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
