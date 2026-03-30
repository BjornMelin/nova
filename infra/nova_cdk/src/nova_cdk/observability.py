# mypy: disable-error-code=import-not-found

"""Observability helpers for the canonical Nova runtime stack."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence

from aws_cdk import (
    RemovalPolicy,
    aws_apigateway as apigw,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_iam as iam,
    aws_logs as logs,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
)
from constructs import Construct

_SECURITY_LOG_RETENTION = logs.RetentionDays.THREE_MONTHS


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
) -> sns.Topic:
    """Create the canonical SNS topic used by runtime alarms."""
    topic = sns.Topic(
        scope,
        "NovaAlarmTopic",
        display_name=f"Nova runtime alarms ({deployment_environment})",
        topic_name=f"nova-runtime-alarms-{deployment_environment}",
    )
    for email in _alarm_notification_emails(scope):
        topic.add_subscription(
            sns_subscriptions.EmailSubscription(email_address=email)
        )
    topic.apply_removal_policy(RemovalPolicy.RETAIN)
    topic.grant_publish(iam.ServicePrincipal("cloudwatch.amazonaws.com"))
    return topic


def create_api_access_log_group(
    scope: Construct,
    *,
    stage_name: str,
) -> logs.LogGroup:
    """Create the retained API Gateway access-log group."""
    return logs.LogGroup(
        scope,
        "NovaApiAccessLogs",
        log_group_name=f"/aws/apigateway/nova-rest-api-access-{stage_name}",
        retention=_SECURITY_LOG_RETENTION,
        removal_policy=RemovalPolicy.RETAIN,
    )


def create_waf_log_group(
    scope: Construct,
    *,
    stage_name: str,
) -> logs.LogGroup:
    """Create the retained WAF log group with the required AWS prefix."""
    return logs.LogGroup(
        scope,
        "NovaWafLogs",
        log_group_name=f"aws-waf-logs-nova-rest-api-{stage_name}",
        retention=_SECURITY_LOG_RETENTION,
        removal_policy=RemovalPolicy.RETAIN,
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
