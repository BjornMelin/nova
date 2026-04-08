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

    _repo_root = Path(__file__).resolve().parents[2]
    _bootstrap_paths: list[str] = [str(_repo_root)]
    for _rel in ("infra/nova_cdk/src", "packages/nova_runtime_support/src"):
        _p = _repo_root / _rel
        if _p.is_dir():
            _bootstrap_paths.append(str(_p))
    sys.path[:0] = _bootstrap_paths

from nova_cdk.runtime_release_manifest import (
    expected_runtime_reserved_concurrency,
    function_logical_id_prefixes,
)
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
_CORS_ALLOWED_HEADERS = {
    "authorization",
    "content-type",
    "idempotency-key",
}
_AWS_CLI_TIMEOUT_SECONDS = 30
_FUNCTION_LOGICAL_ID_PREFIXES = function_logical_id_prefixes()
_APP_CONFIG_COMPLETE_STATES = {"COMPLETE"}


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
    return expected_runtime_reserved_concurrency(
        environment_name=environment_name,
        account_concurrency_limit=account_concurrency_limit,
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


def _stringify_value(value: object) -> str:
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


def _record_assertion(
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
            actual=_stringify_value(actual),
            ok=ok,
        )
    )
    if ok:
        return
    failures.append(
        failure_message
        or f"{name} expected {expected}, got {_stringify_value(actual)}"
    )


def _parse_json_object(payload: bytes | None, *, url: str) -> dict[str, Any]:
    """Parse one JSON response body into an object."""
    if payload is None:
        raise ValueError(f"Missing JSON response body for {url}")
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"Invalid UTF-8 JSON response body for {url}") from exc
    if not isinstance(parsed, dict):
        raise TypeError(f"JSON response must be an object for {url}")
    return parsed


def _ceil_div(numerator: int, denominator: int) -> int:
    """Return the integer ceiling of ``numerator / denominator``."""
    return -(-numerator // denominator)


def _validate_transfer_capabilities(
    *,
    base_url: str,
    representative_upload_bytes: int,
    checks: list[RouteCheck],
    capability_checks: list[AssertionCheck],
    failures: list[str],
) -> None:
    """Validate the public transfer policy envelope exposed by the runtime."""
    result = _request(base_url + DEFAULT_TRANSFER_CAPABILITIES_PATH)
    route_ok = result.error is None and result.status_code == 200
    _record_check(
        checks=checks,
        failures=failures,
        kind="transfer_capabilities",
        method="GET",
        path=DEFAULT_TRANSFER_CAPABILITIES_PATH,
        expected=(
            "status == 200 and payload exposes the effective transfer "
            "policy envelope"
        ),
        result=result,
        ok=route_ok,
    )
    if not route_ok:
        return

    try:
        payload = _parse_json_object(
            result.body,
            url=base_url + DEFAULT_TRANSFER_CAPABILITIES_PATH,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        failures.append(str(exc))
        return

    policy_id = payload.get("policy_id")
    policy_version = payload.get("policy_version")
    max_upload_bytes = payload.get("max_upload_bytes")
    target_upload_part_count = payload.get("target_upload_part_count")
    minimum_part_size_bytes = payload.get("minimum_part_size_bytes")
    maximum_part_size_bytes = payload.get("maximum_part_size_bytes")
    sign_batch_size_hint = payload.get("sign_batch_size_hint")
    accelerate_enabled = payload.get("accelerate_enabled")
    checksum_mode = payload.get("checksum_mode")
    active_multipart_upload_limit = payload.get("active_multipart_upload_limit")
    daily_ingress_budget_bytes = payload.get("daily_ingress_budget_bytes")
    sign_requests_per_upload_limit = payload.get(
        "sign_requests_per_upload_limit"
    )
    large_export_worker_threshold_bytes = payload.get(
        "large_export_worker_threshold_bytes"
    )

    typed_values_ok = all(
        (
            isinstance(policy_id, str) and policy_id.strip(),
            isinstance(policy_version, str) and policy_version.strip(),
            isinstance(max_upload_bytes, int) and max_upload_bytes > 0,
            isinstance(target_upload_part_count, int)
            and target_upload_part_count > 0,
            isinstance(minimum_part_size_bytes, int)
            and minimum_part_size_bytes > 0,
            isinstance(maximum_part_size_bytes, int)
            and maximum_part_size_bytes > 0,
            isinstance(sign_batch_size_hint, int) and sign_batch_size_hint > 0,
            isinstance(accelerate_enabled, bool),
            isinstance(checksum_mode, str) and checksum_mode.strip(),
            isinstance(active_multipart_upload_limit, int)
            and active_multipart_upload_limit > 0,
            isinstance(daily_ingress_budget_bytes, int)
            and daily_ingress_budget_bytes > 0,
            isinstance(sign_requests_per_upload_limit, int)
            and sign_requests_per_upload_limit > 0,
            isinstance(large_export_worker_threshold_bytes, int)
            and large_export_worker_threshold_bytes > 0,
        )
    )
    if not typed_values_ok:
        failures.append(
            "transfer capabilities payload is missing one or more required "
            "typed fields"
        )
        return

    policy_id = cast(str, policy_id)
    policy_version = cast(str, policy_version)
    max_upload_bytes = cast(int, max_upload_bytes)
    target_upload_part_count = cast(int, target_upload_part_count)
    minimum_part_size_bytes = cast(int, minimum_part_size_bytes)
    maximum_part_size_bytes = cast(int, maximum_part_size_bytes)
    sign_batch_size_hint = cast(int, sign_batch_size_hint)
    accelerate_enabled = cast(bool, accelerate_enabled)
    checksum_mode = cast(str, checksum_mode)
    active_multipart_upload_limit = cast(int, active_multipart_upload_limit)
    daily_ingress_budget_bytes = cast(int, daily_ingress_budget_bytes)
    sign_requests_per_upload_limit = cast(int, sign_requests_per_upload_limit)
    large_export_worker_threshold_bytes = cast(
        int, large_export_worker_threshold_bytes
    )

    derived_part_size = min(
        maximum_part_size_bytes,
        max(
            minimum_part_size_bytes,
            _ceil_div(representative_upload_bytes, target_upload_part_count),
        ),
    )
    estimated_part_count = _ceil_div(
        representative_upload_bytes,
        derived_part_size,
    )
    estimated_sign_requests = _ceil_div(
        estimated_part_count,
        sign_batch_size_hint,
    )

    _record_assertion(
        checks=capability_checks,
        failures=failures,
        name="policy_id_non_empty",
        expected="non-empty string",
        actual=policy_id,
        ok=bool(policy_id),
    )
    _record_assertion(
        checks=capability_checks,
        failures=failures,
        name="policy_version_non_empty",
        expected="non-empty string",
        actual=policy_version,
        ok=bool(policy_version),
    )
    _record_assertion(
        checks=capability_checks,
        failures=failures,
        name="representative_upload_allowed",
        expected=f">= {representative_upload_bytes}",
        actual=max_upload_bytes,
        ok=max_upload_bytes >= representative_upload_bytes,
    )
    _record_assertion(
        checks=capability_checks,
        failures=failures,
        name="part_size_bounds_consistent",
        expected="minimum_part_size_bytes <= maximum_part_size_bytes",
        actual={
            "minimum_part_size_bytes": minimum_part_size_bytes,
            "maximum_part_size_bytes": maximum_part_size_bytes,
        },
        ok=minimum_part_size_bytes <= maximum_part_size_bytes,
    )
    _record_assertion(
        checks=capability_checks,
        failures=failures,
        name="checksum_mode_supported",
        expected="one of none, optional, required",
        actual=checksum_mode,
        ok=checksum_mode in {"none", "optional", "required"},
    )
    _record_assertion(
        checks=capability_checks,
        failures=failures,
        name="sign_batch_size_hint_floor",
        expected=">= 32",
        actual=sign_batch_size_hint,
        ok=sign_batch_size_hint >= 32,
    )
    _record_assertion(
        checks=capability_checks,
        failures=failures,
        name="daily_ingress_budget_covers_representative_upload",
        expected=f">= {representative_upload_bytes}",
        actual=daily_ingress_budget_bytes,
        ok=daily_ingress_budget_bytes >= representative_upload_bytes,
    )
    _record_assertion(
        checks=capability_checks,
        failures=failures,
        name="large_export_worker_threshold_above_single_copy_limit",
        expected=f"> {5 * 1024 * 1024 * 1024}",
        actual=large_export_worker_threshold_bytes,
        ok=large_export_worker_threshold_bytes > 5 * 1024 * 1024 * 1024,
    )
    _record_assertion(
        checks=capability_checks,
        failures=failures,
        name="estimated_part_count_for_representative_upload",
        expected="between 1000 and 2000",
        actual=estimated_part_count,
        ok=1000 <= estimated_part_count <= 2000,
    )
    _record_assertion(
        checks=capability_checks,
        failures=failures,
        name="estimated_sign_requests_for_representative_upload",
        expected="<= 64",
        actual=estimated_sign_requests,
        ok=estimated_sign_requests <= 64,
    )
    _record_assertion(
        checks=capability_checks,
        failures=failures,
        name="sign_requests_per_upload_limit_covers_representative_upload",
        expected=f">= {estimated_sign_requests}",
        actual=sign_requests_per_upload_limit,
        ok=sign_requests_per_upload_limit >= estimated_sign_requests,
    )


def _caller_identity_account_id() -> str:
    """Return the AWS account id from the active CLI credentials."""
    payload = _aws_cli_json("sts", "get-caller-identity")
    account_id = payload.get("Account") if isinstance(payload, dict) else None
    if not isinstance(account_id, str) or not account_id.isdigit():
        raise TypeError(
            "aws sts get-caller-identity did not return a valid Account"
        )
    return account_id


def _stack_alarm_names(*, stack_name: str, region: str) -> list[str]:
    """Return the physical alarm names provisioned by one stack."""
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
        raise TypeError("CloudFormation alarm resource payload is malformed")
    alarm_names = [
        str(resource["PhysicalResourceId"]).strip()
        for resource in resources
        if isinstance(resource, dict)
        and resource.get("ResourceType") == "AWS::CloudWatch::Alarm"
        and isinstance(resource.get("PhysicalResourceId"), str)
        and str(resource["PhysicalResourceId"]).strip()
    ]
    return sorted(set(alarm_names))


def _validate_runtime_alarm_states(
    *,
    stack_name: str,
    region: str,
    aws_runtime_checks: list[AssertionCheck],
    aws_failures: list[str],
) -> None:
    """Validate live CloudWatch alarms for one deployed stack."""
    alarm_names = _stack_alarm_names(stack_name=stack_name, region=region)
    _record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="runtime_alarm_inventory_present",
        expected="at least one CloudWatch alarm",
        actual=len(alarm_names),
        ok=bool(alarm_names),
    )
    if not alarm_names:
        return

    alarm_states: dict[str, str] = {}
    for start in range(0, len(alarm_names), 100):
        batch = alarm_names[start : start + 100]
        payload = _aws_cli_json(
            "cloudwatch",
            "describe-alarms",
            "--region",
            region,
            "--alarm-names",
            *batch,
        )
        if not isinstance(payload, dict):
            raise TypeError(
                "aws cloudwatch describe-alarms returned malformed JSON"
            )
        for group_name in ("MetricAlarms", "CompositeAlarms"):
            alarms = payload.get(group_name, [])
            if not isinstance(alarms, list):
                raise TypeError(
                    "aws cloudwatch describe-alarms returned invalid "
                    f"{group_name}"
                )
            for alarm in alarms:
                if not isinstance(alarm, dict):
                    continue
                alarm_name = alarm.get("AlarmName")
                state_value = alarm.get("StateValue")
                if isinstance(alarm_name, str) and isinstance(state_value, str):
                    alarm_states[alarm_name] = state_value

    for alarm_name in alarm_names:
        state_value = alarm_states.get(alarm_name)
        _record_assertion(
            checks=aws_runtime_checks,
            failures=aws_failures,
            name=f"cloudwatch_alarm_state:{alarm_name}",
            expected="state is OK or INSUFFICIENT_DATA",
            actual=state_value,
            ok=state_value in {"OK", "INSUFFICIENT_DATA"},
        )


def _validate_dashboard(
    *,
    deploy_output: dict[str, Any],
    region: str,
    aws_runtime_checks: list[AssertionCheck],
    aws_failures: list[str],
) -> None:
    """Validate the exported observability dashboard exists."""
    stack_outputs = deploy_output["stack_outputs"]
    dashboard_name = stack_outputs.get("NovaObservabilityDashboardName")
    if not isinstance(dashboard_name, str) or not dashboard_name.strip():
        _record_assertion(
            checks=aws_runtime_checks,
            failures=aws_failures,
            name="observability_dashboard_exported",
            expected="non-empty NovaObservabilityDashboardName output",
            actual=dashboard_name,
            ok=False,
        )
        return
    payload = _aws_cli_json(
        "cloudwatch",
        "get-dashboard",
        "--region",
        region,
        "--dashboard-name",
        dashboard_name,
    )
    dashboard_body = (
        payload.get("DashboardBody") if isinstance(payload, dict) else None
    )
    _record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="observability_dashboard_available",
        expected="DashboardBody is a non-empty string",
        actual=dashboard_body,
        ok=isinstance(dashboard_body, str) and bool(dashboard_body.strip()),
    )


def _validate_transfer_policy_rollout(
    *,
    deploy_output: dict[str, Any],
    region: str,
    aws_runtime_checks: list[AssertionCheck],
    aws_failures: list[str],
) -> None:
    """Validate the latest AppConfig transfer-policy deployment completed."""
    stack_outputs = deploy_output["stack_outputs"]
    application_id = stack_outputs.get(
        "NovaTransferPolicyAppConfigApplicationId"
    )
    environment_id = stack_outputs.get(
        "NovaTransferPolicyAppConfigEnvironmentId"
    )
    profile_id = stack_outputs.get("NovaTransferPolicyAppConfigProfileId")
    ids_ok = all(
        isinstance(value, str) and value.strip()
        for value in (application_id, environment_id, profile_id)
    )
    _record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_policy_appconfig_outputs_present",
        expected="application, environment, and profile ids are exported",
        actual={
            "application_id": application_id,
            "environment_id": environment_id,
            "profile_id": profile_id,
        },
        ok=ids_ok,
    )
    if not ids_ok:
        return

    profile_payload = _aws_cli_json(
        "appconfig",
        "get-configuration-profile",
        "--application-id",
        application_id,
        "--configuration-profile-id",
        profile_id,
        "--region",
        region,
    )
    profile_name = (
        profile_payload.get("Name")
        if isinstance(profile_payload, dict)
        else None
    )
    _record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_policy_profile_name_present",
        expected="configuration profile has a non-empty name",
        actual=profile_name,
        ok=isinstance(profile_name, str) and bool(profile_name.strip()),
    )
    if not isinstance(profile_name, str) or not profile_name.strip():
        return

    payload = _aws_cli_json(
        "appconfig",
        "list-deployments",
        "--application-id",
        application_id,
        "--environment-id",
        environment_id,
        "--region",
        region,
        "--max-results",
        "1",
    )
    items = payload.get("Items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        raise TypeError("aws appconfig list-deployments returned invalid Items")
    latest = items[0] if items else None
    state = latest.get("State") if isinstance(latest, dict) else None
    _record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_policy_latest_appconfig_deployment_state",
        expected="latest deployment state is COMPLETE",
        actual=state,
        ok=state in _APP_CONFIG_COMPLETE_STATES,
    )
    deployment_profile_name = (
        latest.get("ConfigurationName") if isinstance(latest, dict) else None
    )
    _record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_policy_latest_appconfig_deployment_profile",
        expected=f"latest deployment configuration name is {profile_name}",
        actual=deployment_profile_name,
        ok=deployment_profile_name == profile_name,
    )


def _validate_transfer_budget(
    *,
    deploy_output: dict[str, Any],
    account_id: str,
    aws_runtime_checks: list[AssertionCheck],
    aws_failures: list[str],
) -> None:
    """Validate the transfer spend budget and notification baseline."""
    stack_outputs = deploy_output["stack_outputs"]
    alarm_topic_arn = stack_outputs.get("NovaAlarmTopicArn")
    _record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="alarm_topic_output_present",
        expected="non-empty NovaAlarmTopicArn output",
        actual=alarm_topic_arn,
        ok=isinstance(alarm_topic_arn, str) and bool(alarm_topic_arn.strip()),
    )
    budget_name = stack_outputs.get("NovaTransferSpendBudgetName")
    if not isinstance(budget_name, str) or not budget_name.strip():
        _record_assertion(
            checks=aws_runtime_checks,
            failures=aws_failures,
            name="transfer_budget_output_present",
            expected="non-empty NovaTransferSpendBudgetName output",
            actual=budget_name,
            ok=False,
        )
        return

    budget_payload = _aws_cli_json(
        "budgets",
        "describe-budget",
        "--account-id",
        account_id,
        "--budget-name",
        budget_name,
    )
    budget = (
        budget_payload.get("Budget")
        if isinstance(budget_payload, dict)
        else None
    )
    budget_limit = (
        budget.get("BudgetLimit", {}) if isinstance(budget, dict) else {}
    )
    budget_amount = (
        budget_limit.get("Amount") if isinstance(budget_limit, dict) else None
    )
    _record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_budget_exists",
        expected="Budget exists and has a positive limit",
        actual=budget_amount,
        ok=isinstance(budget_amount, str) and bool(budget_amount.strip()),
    )

    notifications_payload = _aws_cli_json(
        "budgets",
        "describe-notifications-for-budget",
        "--account-id",
        account_id,
        "--budget-name",
        budget_name,
    )
    notifications = (
        notifications_payload.get("Notifications", [])
        if isinstance(notifications_payload, dict)
        else []
    )
    if not isinstance(notifications, list):
        raise TypeError(
            "aws budgets describe-notifications-for-budget returned invalid "
            "Notifications"
        )
    matching_notifications = [
        notification
        for notification in notifications
        if isinstance(notification, dict)
        and notification.get("NotificationType") == "ACTUAL"
        and notification.get("ComparisonOperator") == "GREATER_THAN"
        and notification.get("ThresholdType") == "PERCENTAGE"
        and notification.get("Threshold") == 80
    ]
    _record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_budget_actual_notification_present",
        expected=(
            "at least one ACTUAL/GREATER_THAN/80/PERCENTAGE budget notification"
        ),
        actual=len(matching_notifications),
        ok=bool(matching_notifications),
    )
    if (
        not matching_notifications
        or not isinstance(alarm_topic_arn, str)
        or not alarm_topic_arn.strip()
    ):
        return

    has_matching_subscriber = False
    for notification in matching_notifications:
        subscribers_payload = _aws_cli_json(
            "budgets",
            "describe-subscribers-for-notification",
            "--account-id",
            account_id,
            "--budget-name",
            budget_name,
            "--notification",
            json.dumps(notification, sort_keys=True),
        )
        subscribers = (
            subscribers_payload.get("Subscribers", [])
            if isinstance(subscribers_payload, dict)
            else []
        )
        if not isinstance(subscribers, list):
            raise TypeError(
                "aws budgets describe-subscribers-for-notification returned "
                "invalid Subscribers"
            )
        if any(
            isinstance(subscriber, dict)
            and subscriber.get("SubscriptionType") == "SNS"
            and subscriber.get("Address") == alarm_topic_arn
            for subscriber in subscribers
        ):
            has_matching_subscriber = True
            break

    _record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_budget_sns_subscriber_matches_alarm_topic",
        expected=f"SNS subscriber {alarm_topic_arn}",
        actual=subscribers,
        ok=has_matching_subscriber,
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
