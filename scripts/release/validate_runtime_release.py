#!/usr/bin/env python3
"""Validate a deployed runtime against the authoritative deploy-output file."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
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
_REPORT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/contracts/release-artifacts-v1.schema.json"
)
REPORT_SCHEMA = json.loads(_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
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
_STANDARD_LAMBDA_ACCOUNT_CONCURRENCY = 1000
_AWS_CLI_TIMEOUT_SECONDS = 30
_PRODUCTION_ENVIRONMENTS = {"prod", "production"}
_API_RESERVED_CONCURRENCY_DEFAULTS = {True: 25, False: 5}
_WORKFLOW_RESERVED_CONCURRENCY_DEFAULTS = {True: 10, False: 2}
_FUNCTION_LOGICAL_ID_PREFIXES = {
    "api": ("NovaApiFunction",),
    "workflow": (
        "ValidateExportFunction",
        "CopyExportFunction",
        "FinalizeExportFunction",
        "FailExportFunction",
    ),
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
class ConcurrencyCheck:
    """Reserved-concurrency validation result for one Lambda function."""

    function_group: str
    function_logical_id: str
    function_name: str
    expected_reserved_concurrency: int | None
    actual_reserved_concurrency: int | None
    ok: bool


@dataclass(frozen=True)
class RequestResult:
    """HTTP response data used by runtime validation checks."""

    status_code: int | None
    headers: dict[str, str]
    body: bytes | None
    error: str | None


def _aws_cli_json(*args: str) -> Any:
    """Run one AWS CLI command and return its JSON payload."""
    command = ["aws", "--no-cli-pager"]
    if "--output" not in args:
        command.extend(["--output", "json"])
    command.extend(args)
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=_AWS_CLI_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("aws CLI is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "aws CLI command timed out after "
            f"{_AWS_CLI_TIMEOUT_SECONDS} seconds: aws {' '.join(args)}"
        ) from exc
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(
            f"aws {' '.join(args)} failed: {stderr or 'unknown error'}"
        )
    stdout = result.stdout.strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"aws {' '.join(args)} returned invalid JSON"
        ) from exc


def _is_production_environment(environment_name: str) -> bool:
    """Return whether one environment name maps to production."""
    return environment_name.strip().casefold() in _PRODUCTION_ENVIRONMENTS


def _account_concurrency_limit(*, region: str) -> int:
    """Return the Lambda regional account concurrency limit."""
    payload = _aws_cli_json(
        "lambda", "get-account-settings", "--region", region
    )
    limit = (
        payload.get("AccountLimit", {}).get("ConcurrentExecutions")
        if isinstance(payload, dict)
        else None
    )
    if not isinstance(limit, int):
        raise TypeError(
            "aws lambda get-account-settings did not return "
            "AccountLimit.ConcurrentExecutions"
        )
    return limit


def _expected_reserved_concurrency(
    *,
    environment_name: str,
    account_concurrency_limit: int,
) -> tuple[int | None, int | None]:
    """Return expected API and workflow reservations for one deploy."""
    is_production = _is_production_environment(environment_name)
    if not is_production and (
        account_concurrency_limit < _STANDARD_LAMBDA_ACCOUNT_CONCURRENCY
    ):
        return None, None
    return (
        _API_RESERVED_CONCURRENCY_DEFAULTS[is_production],
        _WORKFLOW_RESERVED_CONCURRENCY_DEFAULTS[is_production],
    )


def _stack_function_names(
    *,
    stack_name: str,
    region: str,
) -> dict[str, str]:
    """Return logical-to-physical names for runtime Lambda resources."""
    payload = _aws_cli_json(
        "cloudformation",
        "list-stack-resources",
        "--stack-name",
        stack_name,
        "--region",
        region,
    )
    resources = (
        payload.get("StackResourceSummaries", [])
        if isinstance(payload, dict)
        else []
    )
    if not isinstance(resources, list):
        raise TypeError("CloudFormation stack resources payload is malformed")

    names: dict[str, str] = {}
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        if resource.get("ResourceType") != "AWS::Lambda::Function":
            continue
        logical_id = resource.get("LogicalResourceId")
        physical_id = resource.get("PhysicalResourceId")
        if isinstance(logical_id, str) and isinstance(physical_id, str):
            names[logical_id] = physical_id
    return names


def _lookup_function_name(
    function_names: dict[str, str],
    *,
    logical_id_prefix: str,
) -> tuple[str, str]:
    """Return the logical and physical name for one resource prefix."""
    matches = [
        (logical_id, function_name)
        for logical_id, function_name in function_names.items()
        if logical_id.startswith(logical_id_prefix)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one Lambda resource for prefix "
            f"{logical_id_prefix!r}, found {len(matches)}"
        )
    return matches[0]


def _reserved_concurrency_for_function(
    *,
    function_name: str,
    region: str,
) -> int | None:
    """Return one function's configured reserved concurrency, if any."""
    payload = _aws_cli_json(
        "lambda",
        "get-function-concurrency",
        "--function-name",
        function_name,
        "--region",
        region,
    )
    if not isinstance(payload, dict):
        raise TypeError(
            "aws lambda get-function-concurrency returned malformed JSON"
        )
    reserved = payload.get("ReservedConcurrentExecutions")
    if reserved is None:
        return None
    if not isinstance(reserved, int):
        raise TypeError(
            "ReservedConcurrentExecutions must be an integer when present"
        )
    return reserved


def _validate_reserved_concurrency(
    *,
    deploy_output: dict[str, Any],
    failures: list[str],
) -> list[ConcurrencyCheck]:
    """Validate reserved-concurrency truth for deployed runtime Lambdas."""
    region = str(deploy_output["region"])
    stack_name = str(deploy_output["stack_name"])
    environment_name = str(deploy_output["environment"])
    account_concurrency_limit = _account_concurrency_limit(region=region)
    expected_api, expected_workflow = _expected_reserved_concurrency(
        environment_name=environment_name,
        account_concurrency_limit=account_concurrency_limit,
    )
    function_names = _stack_function_names(
        stack_name=stack_name,
        region=region,
    )

    checks: list[ConcurrencyCheck] = []
    for group, prefixes in _FUNCTION_LOGICAL_ID_PREFIXES.items():
        expected = expected_api if group == "api" else expected_workflow
        for prefix in prefixes:
            logical_id, function_name = _lookup_function_name(
                function_names,
                logical_id_prefix=prefix,
            )
            actual = _reserved_concurrency_for_function(
                function_name=function_name,
                region=region,
            )
            ok = actual == expected
            checks.append(
                ConcurrencyCheck(
                    function_group=group,
                    function_logical_id=logical_id,
                    function_name=function_name,
                    expected_reserved_concurrency=expected,
                    actual_reserved_concurrency=actual,
                    ok=ok,
                )
            )
            if not ok:
                failures.append(
                    "reserved concurrency mismatch for "
                    f"{logical_id} ({function_name}): expected "
                    f"{expected!r}, got {actual!r}"
                )
    return checks


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


def load_report_schema() -> dict[str, Any]:
    """Load the canonical post-deploy validation report schema."""
    return cast(
        dict[str, Any], REPORT_SCHEMA["$defs"]["post_deploy_validation_report"]
    )


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
    release_info: dict[str, Any] | None = None
    release_info_ok = release_info_error is None and release_info_status == 200
    if release_info_error is None and release_info_status == 200:
        try:
            release_info = _parse_release_info(
                release_info_body,
                url=f"{base_url}{_RELEASE_INFO_PATH}",
            )
            expected_version = str(deploy_output["runtime_version"])
            actual_version = str(release_info.get("version", "")).strip()
            expected_name = str(deploy_output["runtime_name"])
            actual_name = str(release_info.get("name", "")).strip()
            expected_environment = str(deploy_output["environment"])
            actual_environment = str(
                release_info.get("environment", "")
            ).strip()
            release_info_ok = (
                actual_version == expected_version
                and actual_name == expected_name
                and actual_environment == expected_environment
            )
            if actual_version != expected_version:
                failures.append(
                    "runtime version mismatch: "
                    f"expected {expected_version}, got {actual_version}"
                )
            if actual_name != expected_name:
                failures.append(
                    "runtime name mismatch: "
                    f"expected {expected_name}, got {actual_name}"
                )
            if actual_environment != expected_environment:
                failures.append(
                    "runtime environment mismatch: "
                    f"expected {expected_environment}, got {actual_environment}"
                )
        except (TypeError, ValueError) as exc:
            failures.append(str(exc))
            release_info_ok = False

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
        ok=release_info_ok,
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
    try:
        concurrency_checks = _validate_reserved_concurrency(
            deploy_output=deploy_output,
            failures=failures,
        )
    except Exception as exc:
        failures.append(f"reserved concurrency validation failed: {exc!r}")
        concurrency_checks = []

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
        "concurrency_checks": [asdict(check) for check in concurrency_checks],
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
