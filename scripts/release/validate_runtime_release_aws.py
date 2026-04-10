"""AWS-side runtime release validation checks."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from nova_cdk.runtime_release_manifest import (
    expected_runtime_reserved_concurrency,
    function_logical_id_prefixes,
)
from scripts.release.validate_runtime_release_shared import record_assertion
from scripts.release.validate_runtime_release_types import (
    AssertionCheck,
    ConcurrencyCheck,
)

AWS_CLI_TIMEOUT_SECONDS = 30
FUNCTION_LOGICAL_ID_PREFIXES = function_logical_id_prefixes()
APP_CONFIG_COMPLETE_STATES = {"COMPLETE"}


def aws_cli_json(*args: str) -> Any:
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
            timeout=AWS_CLI_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("aws CLI is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "aws CLI command timed out after "
            f"{AWS_CLI_TIMEOUT_SECONDS} seconds: aws {' '.join(args)}"
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


def account_concurrency_limit(*, region: str) -> int:
    """Return the Lambda regional account concurrency limit."""
    payload = aws_cli_json("lambda", "get-account-settings", "--region", region)
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


def expected_reserved_concurrency(
    *,
    environment_name: str,
    account_concurrency_limit: int,
) -> tuple[int | None, int | None]:
    """Return expected API and workflow reservations for one deploy."""
    return expected_runtime_reserved_concurrency(
        environment_name=environment_name,
        account_concurrency_limit=account_concurrency_limit,
    )


def stack_function_names(*, stack_name: str, region: str) -> dict[str, str]:
    """Return logical-to-physical names for runtime Lambda resources."""
    payload = aws_cli_json(
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


def lookup_function_name(
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


def reserved_concurrency_for_function(
    *,
    function_name: str,
    region: str,
) -> int | None:
    """Return one function's configured reserved concurrency, if any."""
    payload = aws_cli_json(
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


def validate_reserved_concurrency(
    *,
    deploy_output: dict[str, Any],
    failures: list[str],
) -> list[ConcurrencyCheck]:
    """Validate reserved-concurrency truth for deployed runtime Lambdas."""
    region = str(deploy_output["region"])
    stack_name = str(deploy_output["stack_name"])
    environment_name = str(deploy_output["environment"])
    account_limit = account_concurrency_limit(region=region)
    expected_api, expected_workflow = expected_reserved_concurrency(
        environment_name=environment_name,
        account_concurrency_limit=account_limit,
    )
    function_names = stack_function_names(stack_name=stack_name, region=region)

    checks: list[ConcurrencyCheck] = []
    for group, prefixes in FUNCTION_LOGICAL_ID_PREFIXES.items():
        expected = expected_api if group == "api" else expected_workflow
        for prefix in prefixes:
            logical_id, function_name = lookup_function_name(
                function_names,
                logical_id_prefix=prefix,
            )
            actual = reserved_concurrency_for_function(
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


def caller_identity_account_id() -> str:
    """Return the AWS account id from the active CLI credentials."""
    payload = aws_cli_json("sts", "get-caller-identity")
    account_id = payload.get("Account") if isinstance(payload, dict) else None
    if not isinstance(account_id, str) or not account_id.isdigit():
        raise TypeError(
            "aws sts get-caller-identity did not return a valid Account"
        )
    return account_id


def stack_alarm_names(*, stack_name: str, region: str) -> list[str]:
    """Return the physical alarm names provisioned by one stack."""
    payload = aws_cli_json(
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


def validate_runtime_alarm_states(
    *,
    stack_name: str,
    region: str,
    aws_runtime_checks: list[AssertionCheck],
    aws_failures: list[str],
) -> None:
    """Validate live CloudWatch alarms for one deployed stack."""
    alarm_names = stack_alarm_names(stack_name=stack_name, region=region)
    record_assertion(
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
        payload = aws_cli_json(
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
        record_assertion(
            checks=aws_runtime_checks,
            failures=aws_failures,
            name=f"cloudwatch_alarm_state:{alarm_name}",
            expected="state is OK or INSUFFICIENT_DATA",
            actual=state_value,
            ok=state_value in {"OK", "INSUFFICIENT_DATA"},
        )


def validate_dashboard(
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
        record_assertion(
            checks=aws_runtime_checks,
            failures=aws_failures,
            name="observability_dashboard_exported",
            expected="non-empty NovaObservabilityDashboardName output",
            actual=dashboard_name,
            ok=False,
        )
        return
    payload = aws_cli_json(
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
    record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="observability_dashboard_available",
        expected="DashboardBody is a non-empty string",
        actual=dashboard_body,
        ok=isinstance(dashboard_body, str) and bool(dashboard_body.strip()),
    )


def validate_transfer_policy_rollout(
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
    record_assertion(
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

    profile_payload = aws_cli_json(
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
    record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_policy_profile_name_present",
        expected="configuration profile has a non-empty name",
        actual=profile_name,
        ok=isinstance(profile_name, str) and bool(profile_name.strip()),
    )
    if not isinstance(profile_name, str) or not profile_name.strip():
        return

    payload = aws_cli_json(
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
    record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_policy_latest_appconfig_deployment_state",
        expected="latest deployment state is COMPLETE",
        actual=state,
        ok=state in APP_CONFIG_COMPLETE_STATES,
    )
    deployment_profile_name = (
        latest.get("ConfigurationName") if isinstance(latest, dict) else None
    )
    record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_policy_latest_appconfig_deployment_profile",
        expected=f"latest deployment configuration name is {profile_name}",
        actual=deployment_profile_name,
        ok=deployment_profile_name == profile_name,
    )


def validate_transfer_budget(
    *,
    deploy_output: dict[str, Any],
    account_id: str,
    aws_runtime_checks: list[AssertionCheck],
    aws_failures: list[str],
) -> None:
    """Validate the transfer spend budget and notification baseline."""
    stack_outputs = deploy_output["stack_outputs"]
    alarm_topic_arn = stack_outputs.get("NovaAlarmTopicArn")
    record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="alarm_topic_output_present",
        expected="non-empty NovaAlarmTopicArn output",
        actual=alarm_topic_arn,
        ok=isinstance(alarm_topic_arn, str) and bool(alarm_topic_arn.strip()),
    )
    budget_name = stack_outputs.get("NovaTransferSpendBudgetName")
    if not isinstance(budget_name, str) or not budget_name.strip():
        record_assertion(
            checks=aws_runtime_checks,
            failures=aws_failures,
            name="transfer_budget_output_present",
            expected="non-empty NovaTransferSpendBudgetName output",
            actual=budget_name,
            ok=False,
        )
        return

    budget_payload = aws_cli_json(
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
    record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_budget_exists",
        expected="Budget exists and has a positive limit",
        actual=budget_amount,
        ok=isinstance(budget_amount, str) and bool(budget_amount.strip()),
    )

    notifications_payload = aws_cli_json(
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
    record_assertion(
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

    subscribers: list[Any] = []
    has_matching_subscriber = False
    for notification in matching_notifications:
        subscribers_payload = aws_cli_json(
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

    record_assertion(
        checks=aws_runtime_checks,
        failures=aws_failures,
        name="transfer_budget_sns_subscriber_matches_alarm_topic",
        expected=f"SNS subscriber {alarm_topic_arn}",
        actual=subscribers,
        ok=has_matching_subscriber,
    )
