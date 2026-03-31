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
    "/v1/capabilities",
    "/v1/releases/info",
)
DEFAULT_PROTECTED = (
    "GET /metrics/summary",
    "POST /v1/exports",
)
DEFAULT_LEGACY_404 = (
    "/healthz",
    "/readyz",
    "/api/transfers/uploads/initiate",
    "/api/jobs",
    "/api/v1/transfers/uploads/initiate",
)
DEFAULT_CORS_PREFLIGHT_PATH = "/v1/exports"
DEFAULT_CORS_ORIGIN = "http://localhost:3000"
_RELEASE_INFO_PATH = "/v1/releases/info"
_EXACT_CANONICAL_STATUS_CODES: dict[str, set[int]] = {
    "/v1/health/live": {200},
    "/v1/health/ready": {200},
    "/v1/capabilities": {200},
    _RELEASE_INFO_PATH: {200},
}
_PROTECTED_STATUS_CODES = {401, 403}
_CORS_ALLOWED_HEADERS = {
    "authorization",
    "content-type",
    "idempotency-key",
}


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
class RequestResult:
    """HTTP response data used by runtime validation checks."""

    status_code: int | None
    headers: dict[str, str]
    body: bytes | None
    error: str | None


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


def _parse_method_paths(value: str) -> list[tuple[str, str]]:
    """Normalize comma-delimited `METHOD /path` entries."""
    targets: list[tuple[str, str]] = []
    for token in value.split(","):
        candidate = token.strip()
        if not candidate:
            continue
        method, separator, path = candidate.partition(" ")
        if not separator:
            raise ValueError(
                "Protected route entries must use 'METHOD /path' format: "
                f"{candidate!r}"
            )
        normalized_path = path.strip()
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path}"
        targets.append((method.strip().upper(), normalized_path))
    return targets


def _request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> RequestResult:
    """Fetch one URL while preserving HTTP and transport errors."""
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise ValueError(f"Validation fetch requires https URL: {url}")
    request = Request(
        url=url,
        method=method,
        headers=headers or {},
        data=body,
    )
    try:
        with urlopen(request, timeout=10) as response:
            return RequestResult(
                status_code=int(response.getcode()),
                headers={
                    key.lower(): value
                    for key, value in response.headers.items()
                },
                body=response.read(),
                error=None,
            )
    except HTTPError as exc:
        return RequestResult(
            status_code=int(exc.code),
            headers={key.lower(): value for key, value in exc.headers.items()},
            body=exc.read(),
            error=None,
        )
    except URLError as exc:
        return RequestResult(
            status_code=None,
            headers={},
            body=None,
            error=f"Request failed for {url}: {exc}",
        )


def _parse_release_info(payload: bytes | None, *, url: str) -> dict[str, Any]:
    """Parse the release-info response body."""
    if payload is None:
        raise ValueError(f"Missing response body for {url}")
    parsed = json.loads(payload.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise TypeError(f"Release info payload must be a JSON object: {url}")
    return parsed


def _record_check(
    *,
    checks: list[RouteCheck],
    failures: list[str],
    kind: str,
    method: str,
    path: str,
    expected: str,
    result: RequestResult,
    ok: bool,
) -> None:
    """Record one validation check and failure message when it fails."""
    checks.append(
        RouteCheck(
            kind=kind,
            method=method,
            path=path,
            expected=expected,
            status_code=0 if result.status_code is None else result.status_code,
            ok=ok,
        )
    )
    if ok:
        return
    if result.error:
        failures.append(f"{kind} {method} {path} request error: {result.error}")
        return
    failures.append(
        f"{kind} {method} {path} returned "
        f"{0 if result.status_code is None else result.status_code}"
    )


def _json_body() -> bytes:
    """Return the minimal JSON request body used for `/v1/exports` checks."""
    return json.dumps(
        {
            "source_key": "uploads/runtime-validation/source.csv",
            "filename": "source.csv",
        }
    ).encode("utf-8")


def _resolve_cors_origin(
    *, deploy_output: dict[str, Any], cli_origin: str
) -> str:
    """Resolve the browser origin used for CORS and auth-gate checks."""
    override = cli_origin.strip()
    if override:
        return override

    allowed_origins = [
        str(origin).strip() for origin in deploy_output["cors_allowed_origins"]
    ]
    for origin in allowed_origins:
        if origin != "*":
            return origin
    return DEFAULT_CORS_ORIGIN


def _validate_cors_preflight(
    *,
    base_url: str,
    path: str,
    origin: str,
    checks: list[RouteCheck],
    failures: list[str],
) -> None:
    """Validate the browser preflight contract for one protected path."""
    result = _request(
        base_url + path,
        method="OPTIONS",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "Authorization,Content-Type,Idempotency-Key"
            ),
        },
    )
    allow_origin = result.headers.get("access-control-allow-origin", "")
    allow_methods = {
        item.strip().upper()
        for item in result.headers.get(
            "access-control-allow-methods", ""
        ).split(",")
        if item.strip()
    }
    allow_headers = {
        item.strip().lower()
        for item in result.headers.get(
            "access-control-allow-headers", ""
        ).split(",")
        if item.strip()
    }
    ok = (
        result.error is None
        and result.status_code in {200, 204}
        and allow_origin in {"*", origin}
        and "POST" in allow_methods
        and allow_headers >= _CORS_ALLOWED_HEADERS
    )
    _record_check(
        checks=checks,
        failures=failures,
        kind="cors_preflight",
        method="OPTIONS",
        path=path,
        expected=(
            "status in {200,204}, allow-origin matches configured origin or "
            "*, POST allowed, and browser auth headers are allowed"
        ),
        result=result,
        ok=ok,
    )


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
        help="Comma-delimited public canonical paths with exact runtime truth.",
    )
    parser.add_argument(
        "--protected-paths",
        default=",".join(DEFAULT_PROTECTED),
        help="Comma-delimited 'METHOD /path' auth-gate probes.",
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
    parser.add_argument(
        "--cors-preflight-path",
        default=DEFAULT_CORS_PREFLIGHT_PATH,
        help="Protected path used for browser preflight validation.",
    )
    parser.add_argument(
        "--cors-origin",
        default="",
        help="Origin used for browser preflight validation.",
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
    protected_paths = _parse_method_paths(args.protected_paths)
    legacy_paths = _parse_paths(args.legacy_404_paths)
    if not canonical_paths:
        raise SystemExit("Canonical path list resolved to empty")
    if not protected_paths:
        raise SystemExit("Protected path list resolved to empty")
    if not legacy_paths:
        raise SystemExit("Legacy 404 path list resolved to empty")
    cors_preflight_path = _parse_paths(args.cors_preflight_path)
    if len(cors_preflight_path) != 1:
        raise SystemExit("cors-preflight-path must resolve to exactly one path")

    checks: list[RouteCheck] = []
    failures: list[str] = []
    execute_api_endpoint = str(deploy_output["execute_api_endpoint"]).rstrip(
        "/"
    )
    cors_allowed_origins = [
        str(origin).strip() for origin in deploy_output["cors_allowed_origins"]
    ]
    cors_origin = _resolve_cors_origin(
        deploy_output=deploy_output,
        cli_origin=args.cors_origin,
    )

    release_info_result = _request(f"{base_url}{_RELEASE_INFO_PATH}")
    release_info_body = release_info_result.body
    release_info_status = release_info_result.status_code
    release_info_error = release_info_result.error
    _record_check(
        checks=checks,
        failures=failures,
        kind="canonical",
        method="GET",
        path=_RELEASE_INFO_PATH,
        expected=(
            "status == 200 and payload matches deploy-output runtime identity"
        ),
        result=release_info_result,
        ok=release_info_error is None and release_info_status == 200,
    )
    release_info: dict[str, Any] | None = None
    if release_info_error is None and release_info_status == 200:
        try:
            release_info = _parse_release_info(
                release_info_body,
                url=f"{base_url}{_RELEASE_INFO_PATH}",
            )
        except ValueError as exc:
            failures.append(str(exc))

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
        if path == _RELEASE_INFO_PATH:
            continue
        result = _request(base_url + path)
        expected_status_codes = _EXACT_CANONICAL_STATUS_CODES.get(path)
        ok = (
            result.error is None
            and result.status_code is not None
            and (
                result.status_code in expected_status_codes
                if expected_status_codes is not None
                else result.status_code != 404 and result.status_code < 500
            )
        )
        expected = (
            f"status in {sorted(expected_status_codes)}"
            if expected_status_codes is not None
            else "status != 404 and < 500"
        )
        _record_check(
            checks=checks,
            failures=failures,
            kind="canonical",
            method="GET",
            path=path,
            expected=expected,
            result=result,
            ok=ok,
        )

    for method, path in protected_paths:
        result = _request(
            base_url + path,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Origin": cors_origin,
            }
            if method in {"POST", "PUT", "PATCH"}
            else {"Origin": cors_origin},
            body=_json_body() if method in {"POST", "PUT", "PATCH"} else None,
        )
        ok = (
            result.error is None
            and result.status_code in _PROTECTED_STATUS_CODES
            and result.headers.get("access-control-allow-origin", "")
            in {"*", cors_origin}
        )
        _record_check(
            checks=checks,
            failures=failures,
            kind="protected",
            method=method,
            path=path,
            expected=(
                "status in {401,403} without bearer token and allow-origin "
                "matches configured origin or *"
            ),
            result=result,
            ok=ok,
        )

    execute_api_result = _request(f"{execute_api_endpoint}{_RELEASE_INFO_PATH}")
    _record_check(
        checks=checks,
        failures=failures,
        kind="execute_api_disabled",
        method="GET",
        path=_RELEASE_INFO_PATH,
        expected="status == 403 on the disabled execute-api endpoint",
        result=execute_api_result,
        ok=execute_api_result.error is None
        and execute_api_result.status_code == 403,
    )

    _validate_cors_preflight(
        base_url=base_url,
        path=cors_preflight_path[0],
        origin=cors_origin,
        checks=checks,
        failures=failures,
    )

    for path in legacy_paths:
        result = _request(base_url + path)
        _record_check(
            checks=checks,
            failures=failures,
            kind="legacy_404",
            method="GET",
            path=path,
            expected="status == 404",
            result=result,
            ok=result.error is None and result.status_code == 404,
        )

    report = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "execute_api_endpoint": execute_api_endpoint,
        "canonical_paths": canonical_paths,
        "protected_paths": [
            f"{method} {path}" for method, path in protected_paths
        ],
        "legacy_404_paths": legacy_paths,
        "cors_preflight_path": cors_preflight_path[0],
        "cors_allowed_origins": cors_allowed_origins,
        "cors_origin": cors_origin,
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
