# mypy: disable-error-code=import-not-found

"""Security and observability contract tests for the runtime stack."""

from __future__ import annotations

import pytest

from .helpers import (
    load_repo_package_module,
    resources_of_type,
    runtime_stack_template_json,
)

_OBSERVABILITY_MODULE = load_repo_package_module(
    "nova_cdk.observability",
    "infra/nova_cdk/src",
)


def test_runtime_stack_wires_alarm_actions_to_one_sns_topic() -> None:
    """Every runtime alarm should publish to the shared SNS alert topic."""
    template_json = runtime_stack_template_json(
        context={"enable_waf": "true"},
        stack_name="SecurityObservabilityContractStack",
    )
    resources = template_json["Resources"]

    alarms = resources_of_type(resources, "AWS::CloudWatch::Alarm")

    assert alarms
    topics = resources_of_type(resources, "AWS::SNS::Topic")
    assert len(topics) == 1
    topic_logical_id = next(iter(topics))
    topic_output = template_json["Outputs"]["ExportNovaAlarmTopicArn"]["Value"]
    assert topic_output == {"Ref": topic_logical_id}
    for resource in alarms.values():
        alarm_actions = resource["Properties"]["AlarmActions"]
        assert alarm_actions
        assert alarm_actions == [{"Ref": topic_logical_id}]

    outputs = template_json["Outputs"]
    assert "ExportNovaAlarmTopicArn" in outputs
    assert "ExportNovaApiAccessLogGroupName" in outputs
    assert "ExportNovaWafLogGroupName" in outputs
    log_groups = resources_of_type(resources, "Custom::LogRetention")
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

    assert next(iter(topics.values()))["Properties"]["TopicName"] == (
        "nova-runtime-alarms-dev"
    )

    topic_policies = resources_of_type(resources, "AWS::SNS::TopicPolicy")
    assert len(topic_policies) == 1
    policy_document = next(iter(topic_policies.values()))["Properties"][
        "PolicyDocument"
    ]
    statements = policy_document["Statement"]
    assert any(
        statement["Principal"]["Service"] == "cloudwatch.amazonaws.com"
        and statement["Action"] == "sns:Publish"
        for statement in statements
    )

    custom_resources = resources_of_type(resources, "Custom::AWS")
    assert not custom_resources


def test_alarm_notification_email_parser_rejects_malformed_json() -> None:
    """Malformed JSON email input should raise a user-facing TypeError."""
    with pytest.raises(
        TypeError,
        match=(r"alarm_notification_emails JSON input is malformed\."),
    ):
        _OBSERVABILITY_MODULE._parse_alarm_notification_emails("[malformed")


def test_runtime_stack_adds_alarm_topic_email_subscriptions() -> None:
    """Alarm notification emails synthesize native SNS subscriptions."""
    resources = runtime_stack_template_json(
        context={
            "alarm_notification_emails": (
                '["ops@example.com","dev@example.com"]'
            ),
        },
        stack_name="SecurityObservabilityContractStackWithEmail",
    )["Resources"]
    subscriptions = resources_of_type(resources, "AWS::SNS::Subscription")
    assert len(subscriptions) == 2
    endpoints = {
        resource["Properties"]["Endpoint"]
        for resource in subscriptions.values()
    }
    assert endpoints == {"ops@example.com", "dev@example.com"}
    for resource in subscriptions.values():
        assert resource["Properties"]["Protocol"] == "email"
        assert "Ref" in resource["Properties"]["TopicArn"]


def test_runtime_stack_filters_waf_logs_to_security_relevant_actions() -> None:
    """WAF logs: security-relevant actions; secrets redacted."""
    resources = runtime_stack_template_json(
        context={"enable_waf": "true"},
        stack_name="SecurityObservabilityContractWafStack",
    )["Resources"]
    logging_configs = resources_of_type(
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

    log_groups = resources_of_type(resources, "Custom::LogRetention")
    api_access_log_group = next(
        (
            resource
            for resource in log_groups.values()
            if resource["Properties"]
            .get("LogGroupName", "")
            .startswith("/aws/apigateway/nova-rest-api-access-")
        ),
        None,
    )
    assert api_access_log_group is not None, (
        "Expected API access log group with prefix "
        "'/aws/apigateway/nova-rest-api-access-' not found"
    )
    assert api_access_log_group["Properties"]["RetentionInDays"] == 90


def test_non_prod_runtime_stack_omits_waf_outputs_by_default() -> None:
    """Default non-prod stacks should omit WAF outputs and log groups."""
    template_json = runtime_stack_template_json(
        stack_name="SecurityObservabilityNoWafContractStack"
    )
    resources = template_json["Resources"]
    outputs = template_json["Outputs"]

    assert "ExportNovaWafLogGroupName" not in outputs
    assert not resources_of_type(resources, "AWS::WAFv2::WebACL")
    assert not resources_of_type(resources, "AWS::WAFv2::LoggingConfiguration")
