#!/usr/bin/env python3
"""Validate a deployed runtime against the authoritative deploy-output file."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.release import common
from scripts.release.resolve_deploy_output import load_deploy_output

DEFAULT_CANONICAL = (
    "/v1/health/live",
    "/v1/health/ready",
    "/metrics/summary",
    "/v1/capabilities",
    "/v1/releases/info",
)
DEFAULT_LEGACY_404 = (
    "/healthz",
    "/readyz",
    "/api/transfers/uploads/initiate",
    "/api/jobs",
    "/api/v1/transfers/uploads/initiate",
)


@dataclass(frozen=True)
class RouteCheck:
    """Route validation result for one GET request."""

    kind: str
    method: str
    path: str
    expected: str
    status_code: int
    ok: bool


def _parse_paths(value: str) -> list[str]:
    """Normalize a comma-delimited route list."""
    paths: list[str] = []
    for token in value.split(","):
        candidate = token.strip()
        if not candidate:
            continue
        if not candidate.startswith("/"):
            candidate = f"/{candidate}"
        paths.append(candidate)
    return paths


def _fetch(url: str) -> tuple[int | None, bytes | None, str | None]:
    """Fetch one URL while preserving HTTP and transport errors."""
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise ValueError(f"Validation fetch requires https URL: {url}")
    request = Request(url=url, method="GET")  # noqa: S310
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310
            return int(response.getcode()), response.read(), None
    except HTTPError as exc:
        return int(exc.code), exc.read(), None
    except URLError as exc:
        return None, None, f"Request failed for {url}: {exc}"


def _parse_release_info(payload: bytes | None, *, url: str) -> dict[str, Any]:
    """Parse the release-info response body."""
    if payload is None:
        raise ValueError(f"Missing response body for {url}")
    parsed = json.loads(payload.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise TypeError(f"Release info payload must be a JSON object: {url}")
    return parsed


def _args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(
        description="Validate the deployed runtime against deploy-output."
    )
    parser.add_argument("--deploy-output-path", required=True)
    parser.add_argument("--deploy-output-sha256-path")
    parser.add_argument(
        "--canonical-paths",
        default=",".join(DEFAULT_CANONICAL),
        help="Comma-delimited canonical paths that must resolve.",
    )
    parser.add_argument(
        "--legacy-404-paths",
        default=",".join(DEFAULT_LEGACY_404),
        help="Comma-delimited legacy paths that must return 404.",
    )
    parser.add_argument(
        "--report-path",
        default="post-deploy-validation-report.json",
        help="Destination JSON report path.",
    )
    return parser.parse_args()


def main() -> int:
    """Run provenance-aware runtime validation."""
    args = _args()
    deploy_output, deploy_output_sha256 = load_deploy_output(
        deploy_output_path=Path(args.deploy_output_path).resolve(),
        sha256_path=(
            Path(args.deploy_output_sha256_path).resolve()
            if args.deploy_output_sha256_path
            else None
        ),
    )
    base_url = str(deploy_output["public_base_url"]).rstrip("/")
    canonical_paths = _parse_paths(args.canonical_paths)
    legacy_paths = _parse_paths(args.legacy_404_paths)
    if not canonical_paths:
        raise SystemExit("Canonical path list resolved to empty")
    if not legacy_paths:
        raise SystemExit("Legacy 404 path list resolved to empty")

    checks: list[RouteCheck] = []
    failures: list[str] = []

    release_info_status, release_info_body, release_info_error = _fetch(
        f"{base_url}/v1/releases/info"
    )
    release_info: dict[str, Any] | None = None
    if release_info_error is None and release_info_status == 200:
        try:
            release_info = _parse_release_info(
                release_info_body,
                url=f"{base_url}/v1/releases/info",
            )
        except ValueError as exc:
            failures.append(str(exc))
    else:
        if release_info_error:
            failures.append(release_info_error)
        else:
            failures.append(
                "/v1/releases/info returned "
                f"{0 if release_info_status is None else release_info_status}"
            )

    if release_info is not None:
        expected_version = str(deploy_output["runtime_version"])
        actual_version = str(release_info.get("version", "")).strip()
        if actual_version != expected_version:
            failures.append(
                "runtime version mismatch: "
                f"expected {expected_version}, got {actual_version}"
            )

        expected_name = str(deploy_output["runtime_name"])
        actual_name = str(release_info.get("name", "")).strip()
        if actual_name != expected_name:
            failures.append(
                "runtime name mismatch: "
                f"expected {expected_name}, got {actual_name}"
            )

        expected_environment = str(deploy_output["environment"])
        actual_environment = str(release_info.get("environment", "")).strip()
        if actual_environment != expected_environment:
            failures.append(
                "runtime environment mismatch: "
                f"expected {expected_environment}, got {actual_environment}"
            )

    for path in canonical_paths:
        status_code, _, error = _fetch(base_url + path)
        ok = (
            error is None
            and status_code is not None
            and status_code != 404
            and status_code < 500
        )
        checks.append(
            RouteCheck(
                kind="canonical",
                method="GET",
                path=path,
                expected="status != 404 and < 500",
                status_code=0 if status_code is None else status_code,
                ok=ok,
            )
        )
        if not ok:
            if error:
                failures.append(f"canonical path {path} request error: {error}")
            else:
                failures.append(
                    f"canonical path {path} returned "
                    f"{0 if status_code is None else status_code}"
                )

    for path in legacy_paths:
        status_code, _, error = _fetch(base_url + path)
        ok = error is None and status_code == 404
        checks.append(
            RouteCheck(
                kind="legacy_404",
                method="GET",
                path=path,
                expected="status == 404",
                status_code=0 if status_code is None else status_code,
                ok=ok,
            )
        )
        if not ok:
            if error:
                failures.append(f"legacy path {path} request error: {error}")
            else:
                failures.append(
                    f"legacy path {path} returned "
                    f"{0 if status_code is None else status_code}"
                )

    report = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "canonical_paths": canonical_paths,
        "legacy_404_paths": legacy_paths,
        "checks": [asdict(check) for check in checks],
        "status": "failed" if failures else "passed",
        "failures": failures,
        "deploy_output_sha256": deploy_output_sha256,
        "release_commit_sha": deploy_output["release_commit_sha"],
        "runtime_version": deploy_output["runtime_version"],
        "release_info": release_info,
    }
    common.write_json(Path(args.report_path).resolve(), report)

    if failures:
        raise SystemExit("Validation failed: " + "; ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
