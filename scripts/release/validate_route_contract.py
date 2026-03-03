#!/usr/bin/env python3
"""Validate canonical and legacy route expectations against a base URL."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
    """Route status assertion result."""

    kind: str
    path: str
    expected: str
    status_code: int
    ok: bool


def _parse_paths(value: str) -> list[str]:
    paths: list[str] = []
    for token in value.split(","):
        path = token.strip()
        if not path:
            continue
        if not path.startswith("/"):
            path = f"/{path}"
        paths.append(path)
    return paths


def _fetch_status(url: str) -> int:
    request = Request(url=url, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            return int(response.getcode())
    except HTTPError as exc:
        return int(exc.code)
    except URLError as exc:
        raise SystemExit(f"Request failed for {url}: {exc}") from exc


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate canonical and legacy route contract status codes."
    )
    parser.add_argument(
        "--base-url",
        default=(
            os.getenv("VALIDATION_BASE_URL")
            or os.getenv("SERVICE_BASE_URL")
            or ""
        ).strip(),
        help=(
            "Validation base URL. Falls back to "
            "VALIDATION_BASE_URL/SERVICE_BASE_URL."
        ),
    )
    parser.add_argument(
        "--canonical-paths",
        default=os.getenv(
            "VALIDATION_CANONICAL_PATHS", ",".join(DEFAULT_CANONICAL)
        ),
        help=(
            "Comma-delimited canonical paths that must resolve "
            "non-404 and <500."
        ),
    )
    parser.add_argument(
        "--legacy-404-paths",
        default=os.getenv(
            "VALIDATION_LEGACY_404_PATHS", ",".join(DEFAULT_LEGACY_404)
        ),
        help="Comma-delimited legacy paths that must return 404.",
    )
    parser.add_argument(
        "--report-path",
        default="deploy-validation-report.json",
        help="Path for JSON validation report output.",
    )
    return parser.parse_args()


def main() -> int:
    """Run route validation and emit JSON report."""
    args = _args()
    base = args.base_url.strip().rstrip("/")
    if not base:
        raise SystemExit(
            "Provide validation_base_url (preferred) or service_base_url"
        )
    if not base.startswith("https://"):
        raise SystemExit("Validation base URL must start with https://")

    canonical_paths = _parse_paths(args.canonical_paths)
    legacy_paths = _parse_paths(args.legacy_404_paths)
    if not canonical_paths:
        raise SystemExit("VALIDATION_CANONICAL_PATHS resolved to empty list")
    if not legacy_paths:
        raise SystemExit("VALIDATION_LEGACY_404_PATHS resolved to empty list")

    checks: list[RouteCheck] = []
    failures: list[str] = []

    for path in canonical_paths:
        status = _fetch_status(base + path)
        ok = status != 404 and status < 500
        checks.append(
            RouteCheck(
                kind="canonical",
                path=path,
                expected="status != 404 and < 500",
                status_code=status,
                ok=ok,
            )
        )
        if not ok:
            failures.append(f"canonical path {path} returned {status}")

    for path in legacy_paths:
        status = _fetch_status(base + path)
        ok = status == 404
        checks.append(
            RouteCheck(
                kind="legacy_404",
                path=path,
                expected="status == 404",
                status_code=status,
                ok=ok,
            )
        )
        if not ok:
            failures.append(f"legacy path {path} returned {status}")

    report = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "base_url": base,
        "canonical_paths": canonical_paths,
        "legacy_404_paths": legacy_paths,
        "checks": [asdict(check) for check in checks],
        "status": "failed" if failures else "passed",
        "failures": failures,
    }
    with open(args.report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")

    if failures:
        raise SystemExit("Validation failed: " + "; ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
