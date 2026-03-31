# mypy: disable-error-code=import-not-found

"""Observability helpers for the canonical Nova runtime stack."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass

from aws_cdk import (
    Aws,
    aws_apigateway as apigw,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_iam as iam,
    aws_logs as logs,
    aws_sns as sns,
    custom_resources as custom_resources,
)
from constructs import Construct

_SECURITY_LOG_RETENTION = logs.RetentionDays.THREE_MONTHS


@dataclass(frozen=True)
class NamedLogGroup:
    """Describe one named log group ensured via CDK retention management."""

    dependency: logs.LogRetention
    log_group: logs.ILogGroup


def _parse_alarm_notification_emails(raw: object | None) -> list[str]:
    """Normalize optional alarm notification email configuration."""
    if raw is None:
        return []
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return []
        if value.startswith("["):
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise TypeError(
                    "alarm_notification_emails JSON input must decode "
                    "to a list."
                )
            return _parse_alarm_notification_emails(parsed)
        return [
            item
            for item in (entry.strip() for entry in value.split(","))
            if item
        ]
    if isinstance(raw, (list, tuple)):
        return [str(item).strip() for item in raw if str(item).strip()]
    raise TypeError(
        "alarm_notification_emails must be a string or a list of strings."
    )


def _alarm_notification_emails(scope: Construct) -> list[str]:
    """Resolve optional SNS email subscriptions from context or env."""
    return _parse_alarm_notification_emails(
        scope.node.try_get_context("alarm_notification_emails")
        or os.environ.get("ALARM_NOTIFICATION_EMAILS")
    )


def build_api_access_log_format() -> apigw.AccessLogFormat:
    """Return the canonical JSON access-log format for REST API stages."""
    return apigw.AccessLogFormat.custom(
        json.dumps(
            {
                "requestId": "$context.requestId",
                "extendedRequestId": "$context.extendedRequestId",
                "ip": "$context.identity.sourceIp",
                "requestTime": "$context.requestTime",
                "domainName": "$context.domainName",
                "httpMethod": "$context.httpMethod",
                "resourcePath": "$context.resourcePath",
                "protocol": "$context.protocol",
                "status": "$context.status",
                "responseLatency": "$context.responseLatency",
                "responseLength": "$context.responseLength",
                "userAgent": "$context.identity.userAgent",
            },
            separators=(",", ":"),
        )
    )


def create_alarm_topic(
    scope: Construct,
    *,
    deployment_environment: str,
) -> sns.ITopic:
    """Ensure the canonical SNS topic used by runtime alarms exists."""
    topic_name = f"nova-runtime-alarms-{deployment_environment}"
    topic_arn = (
        f"arn:{Aws.PARTITION}:sns:{Aws.REGION}:{Aws.ACCOUNT_ID}:{topic_name}"
    )
    custom_resources.AwsCustomResource(
        scope,
        "NovaAlarmTopicEnsure",
        on_create=custom_resources.AwsSdkCall(
            service="SNS",
            action="createTopic",
            parameters={"Name": topic_name},
            physical_resource_id=custom_resources.PhysicalResourceId.of(
                topic_name
            ),
        ),
        on_update=custom_resources.AwsSdkCall(
            service="SNS",
            action="createTopic",
            parameters={"Name": topic_name},
            physical_resource_id=custom_resources.PhysicalResourceId.of(
                topic_name
            ),
        ),
        policy=custom_resources.AwsCustomResourcePolicy.from_sdk_calls(
            resources=custom_resources.AwsCustomResourcePolicy.ANY_RESOURCE
        ),
        install_latest_aws_sdk=False,
    )
    topic = sns.Topic.from_topic_arn(
        scope,
        "NovaAlarmTopic",
        topic_arn=topic_arn,
    )
    for index, email in enumerate(_alarm_notification_emails(scope), start=1):
        sns.Subscription(
            scope,
            f"NovaAlarmTopicEmailSubscription{index}",
            endpoint=email,
            protocol=sns.SubscriptionProtocol.EMAIL,
            topic=topic,
        )
    topic.add_to_resource_policy(
        iam.PolicyStatement(
            actions=["sns:Publish"],
            principals=[iam.ServicePrincipal("cloudwatch.amazonaws.com")],
            resources=[topic.topic_arn],
        )
    )
    return topic


def create_api_access_log_group(
    scope: Construct,
    *,
    stage_name: str,
) -> NamedLogGroup:
    """Ensure the named API Gateway access-log group exists with retention."""
    log_group_name = f"/aws/apigateway/nova-rest-api-access-{stage_name}"
    retention = logs.LogRetention(
        scope,
        "NovaApiAccessLogsRetention",
        log_group_name=log_group_name,
        retention=_SECURITY_LOG_RETENTION,
    )
    return NamedLogGroup(
        dependency=retention,
        log_group=logs.LogGroup.from_log_group_name(
            scope,
            "NovaApiAccessLogs",
            log_group_name,
        ),
    )


def create_waf_log_group(
    scope: Construct,
    *,
    stage_name: str,
) -> NamedLogGroup:
    """Ensure the named WAF log group exists with retention."""
    log_group_name = f"aws-waf-logs-nova-rest-api-{stage_name}"
    retention = logs.LogRetention(
        scope,
        "NovaWafLogsRetention",
        log_group_name=log_group_name,
        retention=_SECURITY_LOG_RETENTION,
    )
    return NamedLogGroup(
        dependency=retention,
        log_group=logs.LogGroup.from_log_group_name(
            scope,
            "NovaWafLogs",
            log_group_name,
        ),
    )


def add_alarm_actions(
    *,
    alarms: Sequence[cloudwatch.Alarm],
    topic: sns.ITopic,
) -> None:
    """Attach the canonical SNS alarm action to each alarm."""
    alarm_action = cloudwatch_actions.SnsAction(topic)
    for alarm in alarms:
        alarm.add_alarm_action(alarm_action)
