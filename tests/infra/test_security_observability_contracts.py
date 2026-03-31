# mypy: disable-error-code=import-not-found

"""Security and observability contract tests for the runtime stack."""

from __future__ import annotations

import json
from typing import Any, cast

from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from .helpers import load_repo_package_module

_RUNTIME_STACK_MODULE = load_repo_package_module(
    "nova_cdk.runtime_stack",
    "infra/nova_cdk/src",
)
NovaRuntimeStack = _RUNTIME_STACK_MODULE.NovaRuntimeStack


def _context_for_region(region: str) -> dict[str, str]:
    """Return the minimum valid stack context for one region."""
    return {
        "api_domain_name": "api.dev.example.com",
        "api_lambda_artifact_bucket": (
            "nova-ci-artifacts-111111111111-us-east-1"
        ),
        "api_lambda_artifact_key": (
            "runtime/nova-file-api/"
            "01234567-89ab-cdef-0123-456789abcdef/"
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef/"
            "nova-file-api-lambda.zip"
        ),
        "api_lambda_artifact_sha256": (
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
        "certificate_arn": (
            f"arn:aws:acm:{region}:111111111111:"
            "certificate/12345678-1234-1234-1234-123456789012"
        ),
        "hosted_zone_id": "Z1234567890EXAMPLE",
        "hosted_zone_name": "example.com",
        "jwt_audience": "api://nova",
        "jwt_issuer": "https://issuer.example.com/",
        "jwt_jwks_url": "https://issuer.example.com/.well-known/jwks.json",
    }


def _template_json(
    *,
    context: dict[str, str] | None = None,
    region: str = "us-west-2",
) -> dict[str, Any]:
    """Return the synthesized template JSON for one stack context."""
    app = App(context=context or _context_for_region(region))
    stack = NovaRuntimeStack(
        app,
        "SecurityObservabilityContractStack",
        env=Environment(account="111111111111", region=region),
    )
    return cast(dict[str, Any], Template.from_stack(stack).to_json())


def _resources_of_type(
    resources: dict[str, Any],
    type_name: str,
) -> dict[str, dict[str, Any]]:
    """Return all template resources of one CloudFormation type."""
    return {
        logical_id: resource
        for logical_id, resource in resources.items()
        if resource["Type"] == type_name
    }


def test_runtime_stack_wires_alarm_actions_to_one_sns_topic() -> None:
    """Every runtime alarm should publish to the shared SNS alert topic."""
    template_json = _template_json()
    resources = template_json["Resources"]

    alarms = _resources_of_type(resources, "AWS::CloudWatch::Alarm")

    assert alarms
    topic_output = template_json["Outputs"]["ExportNovaAlarmTopicArn"]["Value"]
    assert "nova-runtime-alarms-dev" in json.dumps(
        topic_output,
        sort_keys=True,
    )
    for resource in alarms.values():
        alarm_actions = resource["Properties"]["AlarmActions"]
        assert alarm_actions
        assert "nova-runtime-alarms-dev" in json.dumps(
            alarm_actions,
            sort_keys=True,
        )

    outputs = template_json["Outputs"]
    assert "ExportNovaAlarmTopicArn" in outputs
    assert "ExportNovaApiAccessLogGroupName" in outputs
    assert "ExportNovaWafLogGroupName" in outputs
    log_groups = _resources_of_type(resources, "Custom::LogRetention")
    assert any(
        resource["Properties"].get("LogGroupName")
        == "/aws/apigateway/nova-rest-api-access-dev"
        and resource["Properties"].get("RetentionInDays") == 90
        for resource in log_groups.values()
    )
    assert any(
        resource["Properties"].get("LogGroupName")
        == "aws-waf-logs-nova-rest-api-dev"
        and resource["Properties"].get("RetentionInDays") == 90
        for resource in log_groups.values()
    )
    assert (
        outputs["ExportNovaApiAccessLogGroupName"]["Value"]
        == "/aws/apigateway/nova-rest-api-access-dev"
    )
    assert (
        outputs["ExportNovaWafLogGroupName"]["Value"]
        == "aws-waf-logs-nova-rest-api-dev"
    )


def test_runtime_stack_filters_waf_logs_to_security_relevant_actions() -> None:
    """WAF logs: security-relevant actions; secrets redacted."""
    resources = _template_json()["Resources"]
    logging_configs = _resources_of_type(
        resources,
        "AWS::WAFv2::LoggingConfiguration",
    )
    assert len(logging_configs) == 1
    logging_props = next(iter(logging_configs.values()))["Properties"]

    logging_filter = logging_props["LoggingFilter"]
    assert logging_filter["DefaultBehavior"] == "DROP"
    assert logging_filter["Filters"] == [
        {
            "Behavior": "KEEP",
            "Conditions": [
                {"ActionCondition": {"Action": "BLOCK"}},
                {"ActionCondition": {"Action": "COUNT"}},
            ],
            "Requirement": "MEETS_ANY",
        }
    ]

    log_groups = _resources_of_type(resources, "Custom::LogRetention")
    api_access_log_group = next(
        resource
        for resource in log_groups.values()
        if resource["Properties"]
        .get("LogGroupName", "")
        .startswith("/aws/apigateway/nova-rest-api-access-")
    )
    assert api_access_log_group["Properties"]["RetentionInDays"] == 90
