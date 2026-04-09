#!/usr/bin/env python3
"""Validate a deployed runtime against the authoritative deploy-output file."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

if __package__ in {None, ""}:
    import sys

    _repo_root = Path(__file__).resolve().parents[2]
    _bootstrap_paths: list[str] = [str(_repo_root)]
    for _rel in ("infra/nova_cdk/src", "packages/nova_runtime_support/src"):
        _p = _repo_root / _rel
        if _p.is_dir():
            _bootstrap_paths.append(str(_p))
    sys.path[:0] = _bootstrap_paths

from scripts.release import common, validate_runtime_release_http as http_checks
from scripts.release.resolve_deploy_output import load_deploy_output
from scripts.release.validate_runtime_release_types import (
    AssertionCheck,
    ConcurrencyCheck,
    RequestResult,
    RouteCheck,
)

try:
    from scripts.release import validate_runtime_release_aws as aws_checks
except ModuleNotFoundError as exc:
    if exc.name in {"nova_cdk", "nova_runtime_support"}:
        raise RuntimeError(
            "validate_runtime_release.py requires workspace packages "
            "`nova_cdk` and `nova_runtime_support` to be importable. Run "
            "this script via `uv run python scripts/release/"
            "validate_runtime_release.py` or from an environment where the "
            "workspace packages are installed."
        ) from exc
    raise

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
DEFAULT_TRANSFER_CAPABILITIES_PATH = "/v1/capabilities/transfers"
DEFAULT_REPRESENTATIVE_UPLOAD_BYTES = 500 * 1024 * 1024 * 1024
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
_CORS_ALLOWED_HEADERS = http_checks.CORS_ALLOWED_HEADERS
_AWS_CLI_TIMEOUT_SECONDS = aws_checks.AWS_CLI_TIMEOUT_SECONDS
_FUNCTION_LOGICAL_ID_PREFIXES = aws_checks.FUNCTION_LOGICAL_ID_PREFIXES
_APP_CONFIG_COMPLETE_STATES = aws_checks.APP_CONFIG_COMPLETE_STATES
_AWS_CLI_JSON_IMPL = aws_checks.aws_cli_json
_REQUEST_IMPL = http_checks.request
_RECORD_CHECK_IMPL = http_checks.record_check


def _with_aws_cli_override() -> None:
    """Keep split AWS checks compatible with module-level test patches."""
    setattr(aws_checks, "aws_cli_json", _aws_cli_json)  # noqa: B010


def _with_http_request_override() -> None:
    """Keep split HTTP checks compatible with module-level test patches."""
    setattr(http_checks, "request", _request)  # noqa: B010
    setattr(http_checks, "record_check", _record_check)  # noqa: B010


def _aws_cli_json(*args: str) -> Any:
    """Run one AWS CLI command and return its JSON payload."""
    return _AWS_CLI_JSON_IMPL(*args)


def _account_concurrency_limit(*, region: str) -> int:
    """Return the Lambda regional account concurrency limit."""
    _with_aws_cli_override()
    return aws_checks.account_concurrency_limit(region=region)


def _expected_reserved_concurrency(
    *,
    environment_name: str,
    account_concurrency_limit: int,
) -> tuple[int | None, int | None]:
    """Return expected API and workflow reservations for one deploy."""
    return aws_checks.expected_reserved_concurrency(
        environment_name=environment_name,
        account_concurrency_limit=account_concurrency_limit,
    )


def _stack_function_names(*, stack_name: str, region: str) -> dict[str, str]:
    """Return logical-to-physical names for runtime Lambda resources."""
    _with_aws_cli_override()
    return aws_checks.stack_function_names(
        stack_name=stack_name,
        region=region,
    )


def _lookup_function_name(
    function_names: dict[str, str],
    *,
    logical_id_prefix: str,
) -> tuple[str, str]:
    """Return the logical and physical name for one resource prefix."""
    return aws_checks.lookup_function_name(
        function_names,
        logical_id_prefix=logical_id_prefix,
    )


def _reserved_concurrency_for_function(
    *,
    function_name: str,
    region: str,
) -> int | None:
    """Return one function's configured reserved concurrency, if any."""
    _with_aws_cli_override()
    return aws_checks.reserved_concurrency_for_function(
        function_name=function_name,
        region=region,
    )


def _validate_reserved_concurrency(
    *,
    deploy_output: dict[str, Any],
    failures: list[str],
) -> list[ConcurrencyCheck]:
    """Validate reserved-concurrency truth for deployed runtime Lambdas."""
    _with_aws_cli_override()
    return aws_checks.validate_reserved_concurrency(
        deploy_output=deploy_output,
        failures=failures,
    )


def _parse_json_object(payload: bytes | None, *, url: str) -> dict[str, Any]:
    """Parse one JSON response body into an object."""
    return http_checks.parse_json_object(payload, url=url)


def _ceil_div(numerator: int, denominator: int) -> int:
    """Return the integer ceiling of ``numerator / denominator``."""
    return http_checks.ceil_div(numerator, denominator)


def _validate_transfer_capabilities(
    *,
    base_url: str,
    representative_upload_bytes: int,
    checks: list[RouteCheck],
    capability_checks: list[AssertionCheck],
    failures: list[str],
) -> None:
    """Validate the public transfer policy envelope exposed by the runtime."""
    _with_http_request_override()
    http_checks.validate_transfer_capabilities(
        base_url=base_url,
        representative_upload_bytes=representative_upload_bytes,
        checks=checks,
        capability_checks=capability_checks,
        failures=failures,
    )


def _caller_identity_account_id() -> str:
    """Return the AWS account id from the active CLI credentials."""
    _with_aws_cli_override()
    return aws_checks.caller_identity_account_id()


def _stack_alarm_names(*, stack_name: str, region: str) -> list[str]:
    """Return the physical alarm names provisioned by one stack."""
    _with_aws_cli_override()
    return aws_checks.stack_alarm_names(
        stack_name=stack_name,
        region=region,
    )


def _validate_runtime_alarm_states(
    *,
    stack_name: str,
    region: str,
    aws_runtime_checks: list[AssertionCheck],
    aws_failures: list[str],
) -> None:
    """Validate live CloudWatch alarms for one deployed stack."""
    _with_aws_cli_override()
    aws_checks.validate_runtime_alarm_states(
        stack_name=stack_name,
        region=region,
        aws_runtime_checks=aws_runtime_checks,
        aws_failures=aws_failures,
    )


def _validate_dashboard(
    *,
    deploy_output: dict[str, Any],
    region: str,
    aws_runtime_checks: list[AssertionCheck],
    aws_failures: list[str],
) -> None:
    """Validate the exported observability dashboard exists."""
    _with_aws_cli_override()
    aws_checks.validate_dashboard(
        deploy_output=deploy_output,
        region=region,
        aws_runtime_checks=aws_runtime_checks,
        aws_failures=aws_failures,
    )


def _validate_transfer_policy_rollout(
    *,
    deploy_output: dict[str, Any],
    region: str,
    aws_runtime_checks: list[AssertionCheck],
    aws_failures: list[str],
) -> None:
    """Validate the latest AppConfig transfer-policy deployment completed."""
    _with_aws_cli_override()
    aws_checks.validate_transfer_policy_rollout(
        deploy_output=deploy_output,
        region=region,
        aws_runtime_checks=aws_runtime_checks,
        aws_failures=aws_failures,
    )


def _validate_transfer_budget(
    *,
    deploy_output: dict[str, Any],
    account_id: str,
    aws_runtime_checks: list[AssertionCheck],
    aws_failures: list[str],
) -> None:
    """Validate the transfer spend budget and notification baseline."""
    _with_aws_cli_override()
    aws_checks.validate_transfer_budget(
        deploy_output=deploy_output,
        account_id=account_id,
        aws_runtime_checks=aws_runtime_checks,
        aws_failures=aws_failures,
    )


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
    return _REQUEST_IMPL(
        url,
        method=method,
        headers=headers,
        body=body,
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
    _RECORD_CHECK_IMPL(
        checks=checks,
        failures=failures,
        kind=kind,
        method=method,
        path=path,
        expected=expected,
        result=result,
        ok=ok,
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
    _with_http_request_override()
    http_checks.validate_cors_preflight(
        base_url=base_url,
        path=path,
        origin=origin,
        checks=checks,
        failures=failures,
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
    parser.add_argument(
        "--representative-upload-bytes",
        type=int,
        default=DEFAULT_REPRESENTATIVE_UPLOAD_BYTES,
        help=(
            "Representative upload size used when validating the live "
            "transfer policy envelope."
        ),
    )
    parser.add_argument(
        "--aws-runtime-checks",
        choices=("required", "skip"),
        default="required",
        help=(
            "Require live AWS read access for concurrency, alarm, "
            "AppConfig, dashboard, and budget checks, or skip them."
        ),
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
    capability_checks: list[AssertionCheck] = []
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
    _validate_transfer_capabilities(
        base_url=base_url,
        representative_upload_bytes=args.representative_upload_bytes,
        checks=checks,
        capability_checks=capability_checks,
        failures=failures,
    )

    concurrency_checks: list[ConcurrencyCheck] = []
    aws_runtime_checks: list[AssertionCheck] = []
    aws_runtime_checks_status = "skipped"
    if args.aws_runtime_checks != "skip":
        aws_failures: list[str] = []
        region = str(deploy_output["region"])
        stack_name = str(deploy_output["stack_name"])

        try:
            concurrency_checks = _validate_reserved_concurrency(
                deploy_output=deploy_output,
                failures=aws_failures,
            )
        except Exception as exc:
            aws_failures.append(
                f"reserved concurrency validation failed: {exc!r}"
            )

        account_id: str | None = None
        try:
            account_id = _caller_identity_account_id()
        except Exception as exc:
            aws_failures.append(f"aws caller identity lookup failed: {exc!r}")

        try:
            _validate_runtime_alarm_states(
                stack_name=stack_name,
                region=region,
                aws_runtime_checks=aws_runtime_checks,
                aws_failures=aws_failures,
            )
        except Exception as exc:
            aws_failures.append(f"runtime alarm validation failed: {exc!r}")

        try:
            _validate_dashboard(
                deploy_output=deploy_output,
                region=region,
                aws_runtime_checks=aws_runtime_checks,
                aws_failures=aws_failures,
            )
        except Exception as exc:
            aws_failures.append(
                f"observability dashboard validation failed: {exc!r}"
            )

        try:
            _validate_transfer_policy_rollout(
                deploy_output=deploy_output,
                region=region,
                aws_runtime_checks=aws_runtime_checks,
                aws_failures=aws_failures,
            )
        except Exception as exc:
            aws_failures.append(f"AppConfig rollout validation failed: {exc!r}")

        if account_id is not None:
            try:
                _validate_transfer_budget(
                    deploy_output=deploy_output,
                    account_id=account_id,
                    aws_runtime_checks=aws_runtime_checks,
                    aws_failures=aws_failures,
                )
            except Exception as exc:
                aws_failures.append(
                    f"transfer budget validation failed: {exc!r}"
                )

        aws_runtime_checks_status = "failed" if aws_failures else "passed"
        failures.extend(aws_failures)

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
        "capability_checks": [asdict(check) for check in capability_checks],
        "concurrency_checks": [asdict(check) for check in concurrency_checks],
        "aws_runtime_checks_status": aws_runtime_checks_status,
        "aws_runtime_checks": [asdict(check) for check in aws_runtime_checks],
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
