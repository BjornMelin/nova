#!/usr/bin/env python3
"""Validate canonical and legacy route expectations.

The script checks runtime and auth base URLs against the hard-cut route
surface and confirms retired legacy paths stay retired.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_CANONICAL = (
    "GET:/v1/health/live=200",
    "GET:/v1/health/ready=200",
    "GET:/metrics/summary=401|403",
    "GET:/v1/capabilities=200",
    "GET:/v1/releases/info=200",
)
DEFAULT_LEGACY_404 = (
    "/healthz",
    "/readyz",
    "/api/transfers/uploads/initiate",
    "/api/jobs",
    "/api/v1/transfers/uploads/initiate",
)
DEFAULT_AUTH_CANONICAL = (
    "GET:/v1/health/live=200",
    "GET:/v1/health/ready=200",
    "POST:/v1/token/verify=400|401|403|415|422",
    "POST:/v1/token/introspect=400|401|403|415|422",
)


@dataclass(frozen=True)
class RouteExpectation:
    """Expected route/method pair for validation."""

    method: str
    path: str
    allowed_statuses: tuple[int, ...]


@dataclass(frozen=True)
class RouteCheck:
    """Route status assertion result."""

    kind: str
    method: str
    path: str
    expected: str
    status_code: int
    ok: bool


def _parse_paths(
    value: str,
    *,
    default_statuses: tuple[int, ...],
) -> list[RouteExpectation]:
    paths: list[RouteExpectation] = []
    for token in value.split(","):
        raw = token.strip()
        if not raw:
            continue
        allowed_statuses = default_statuses
        if "=" in raw:
            raw, statuses_raw = raw.rsplit("=", 1)
            allowed_statuses = tuple(
                int(status.strip())
                for status in statuses_raw.split("|")
                if status.strip()
            )
            if not allowed_statuses:
                raise ValueError(
                    "route expectation must include at least one status code"
                )
        method = "GET"
        path = raw
        if ":/" in raw:
            method, path = raw.split(":", 1)
            method = method.strip().upper()
        if not path.startswith("/"):
            path = f"/{path}"
        paths.append(
            RouteExpectation(
                method=method,
                path=path,
                allowed_statuses=allowed_statuses,
            )
        )
    return paths


def _fetch_status(
    *,
    url: str,
    method: str,
) -> tuple[int | None, str | None]:
    """Fetch status for a URL while preserving transport errors."""
    request = Request(url=url, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            return int(response.getcode()), None
    except HTTPError as exc:
        return int(exc.code), None
    except URLError as exc:
        return None, f"Request failed for {url}: {exc}"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate canonical and legacy route contract status codes."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("VALIDATION_BASE_URL", "").strip(),
        help="Validation base URL. Falls back to VALIDATION_BASE_URL.",
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
        "--auth-base-url",
        default=os.getenv("AUTH_VALIDATION_BASE_URL", "").strip(),
        help=(
            "Optional auth validation base URL. Falls back to "
            "AUTH_VALIDATION_BASE_URL."
        ),
    )
    parser.add_argument(
        "--auth-canonical-paths",
        default=os.getenv(
            "AUTH_VALIDATION_CANONICAL_PATHS",
            ",".join(DEFAULT_AUTH_CANONICAL),
        ),
        help=(
            "Comma-delimited auth canonical paths. METHOD:/path is supported; "
            "plain /path defaults to GET."
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


def _validate_target(
    *,
    name: str,
    base_url: str,
    canonical_paths: list[RouteExpectation],
    legacy_paths: list[RouteExpectation],
) -> dict[str, Any]:
    checks: list[RouteCheck] = []
    failures: list[str] = []

    for expectation in canonical_paths:
        status, error = _fetch_status(
            url=base_url + expectation.path,
            method=expectation.method,
        )
        ok = (
            error is None
            and status is not None
            and status in expectation.allowed_statuses
        )
        status_code = status if status is not None else 0
        checks.append(
            RouteCheck(
                kind="canonical",
                method=expectation.method,
                path=expectation.path,
                expected=(
                    "status in "
                    + ",".join(
                        str(value) for value in expectation.allowed_statuses
                    )
                ),
                status_code=status_code,
                ok=ok,
            )
        )
        if not ok:
            if error:
                failures.append(
                    f"{name} canonical {expectation.method} "
                    f"{expectation.path} request error: {error}"
                )
            else:
                failures.append(
                    f"{name} canonical {expectation.method} "
                    f"{expectation.path} returned {status_code}"
                )

    for expectation in legacy_paths:
        status, error = _fetch_status(
            url=base_url + expectation.path,
            method=expectation.method,
        )
        ok = error is None and status == 404
        status_code = status if status is not None else 0
        checks.append(
            RouteCheck(
                kind="legacy_404",
                method=expectation.method,
                path=expectation.path,
                expected="status == 404",
                status_code=status_code,
                ok=ok,
            )
        )
        if not ok:
            if error:
                failures.append(
                    f"{name} legacy {expectation.method} "
                    f"{expectation.path} request error: {error}"
                )
            else:
                failures.append(
                    f"{name} legacy {expectation.method} "
                    f"{expectation.path} returned {status_code}"
                )

    return {
        "base_url": base_url,
        "canonical_paths": [item.path for item in canonical_paths],
        "legacy_404_paths": [item.path for item in legacy_paths],
        "checks": [asdict(check) for check in checks],
        "status": "failed" if failures else "passed",
        "failures": failures,
    }


def main() -> int:
    """Run route validation and emit JSON report.

    Returns:
        int: 0 when all expected routes pass validation.

    Raises:
        SystemExit: If configuration is invalid or validation checks fail.
    """
    args = _args()
    base = args.base_url.strip().rstrip("/")
    if not base:
        raise SystemExit("Provide validation_base_url")
    if not base.startswith("https://"):
        raise SystemExit("Validation base URL must start with https://")
    auth_base = args.auth_base_url.strip().rstrip("/")
    if auth_base and not auth_base.startswith("https://"):
        raise SystemExit("Auth validation base URL must start with https://")

    canonical_paths = _parse_paths(
        args.canonical_paths,
        default_statuses=(200,),
    )
    legacy_paths = _parse_paths(
        args.legacy_404_paths,
        default_statuses=(404,),
    )
    auth_canonical_paths = _parse_paths(
        args.auth_canonical_paths,
        default_statuses=(200,),
    )
    if not canonical_paths:
        raise SystemExit("VALIDATION_CANONICAL_PATHS resolved to empty list")
    file_target = _validate_target(
        name="file",
        base_url=base,
        canonical_paths=canonical_paths,
        legacy_paths=legacy_paths,
    )
    auth_target: dict[str, Any] | None = None
    failures = list(file_target["failures"])
    if auth_base:
        if not auth_canonical_paths:
            raise SystemExit(
                "AUTH_VALIDATION_CANONICAL_PATHS resolved to empty list"
            )
        auth_target = _validate_target(
            name="auth",
            base_url=auth_base,
            canonical_paths=auth_canonical_paths,
            legacy_paths=[],
        )
        failures.extend(auth_target["failures"])

    report = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "base_url": file_target["base_url"],
        "canonical_paths": file_target["canonical_paths"],
        "legacy_404_paths": file_target["legacy_404_paths"],
        "checks": file_target["checks"],
        "status": "failed" if failures else "passed",
        "failures": failures,
    }
    if auth_target is not None:
        report["auth_target"] = auth_target
    with open(args.report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")

    if failures:
        raise SystemExit("Validation failed: " + "; ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
