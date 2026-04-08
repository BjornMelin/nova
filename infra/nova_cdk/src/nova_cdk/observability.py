"""Observability helpers for the canonical Nova runtime stack."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass

from aws_cdk import (
    aws_apigateway as apigw,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_iam as iam,
    aws_logs as logs,
    aws_sns as sns,
    custom_resources as cr,
)
from constructs import Construct

from .context_inputs import parse_string_list

_SECURITY_LOG_RETENTION = logs.RetentionDays.THREE_MONTHS


@dataclass(frozen=True)
class NamedLogGroup:
    """Describe one named log group ensured via CDK retention management."""

    dependency: logs.LogRetention
    log_group: logs.ILogGroup


def _parse_alarm_notification_emails(raw: object | None) -> list[str]:
    """Normalize optional alarm notification email configuration."""
    return parse_string_list(raw, key="alarm_notification_emails")


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
    topic_ensure = cr.AwsCustomResource(
        scope,
        "NovaAlarmTopicEnsure",
        install_latest_aws_sdk=False,
        on_create=cr.AwsSdkCall(
            service="SNS",
            action="createTopic",
            parameters={"Name": topic_name},
            physical_resource_id=cr.PhysicalResourceId.of(topic_name),
        ),
        on_update=cr.AwsSdkCall(
            service="SNS",
            action="createTopic",
            parameters={"Name": topic_name},
            physical_resource_id=cr.PhysicalResourceId.of(topic_name),
        ),
        policy=cr.AwsCustomResourcePolicy.from_statements(
            [
                iam.PolicyStatement(
                    actions=["sns:CreateTopic"],
                    resources=["*"],
                )
            ]
        ),
    )
    topic = sns.Topic.from_topic_arn(
        scope,
        "NovaAlarmTopic",
        topic_arn=topic_ensure.get_response_field("TopicArn"),
    )
    topic_policy = sns.CfnTopicPolicy(
        scope,
        "NovaAlarmTopicPolicy",
        topics=[topic.topic_arn],
        policy_document={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": [
                            "budgets.amazonaws.com",
                            "cloudwatch.amazonaws.com",
                        ]
                    },
                    "Action": "sns:Publish",
                    "Resource": topic.topic_arn,
                }
            ],
        },
    )
    topic_policy.node.add_dependency(topic_ensure)
    for index, email in enumerate(_alarm_notification_emails(scope), start=1):
        subscription = sns.Subscription(
            scope,
            f"NovaAlarmTopicEmailSubscription{index}",
            endpoint=email,
            protocol=sns.SubscriptionProtocol.EMAIL,
            topic=topic,
        )
        subscription.node.add_dependency(topic_ensure)
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
