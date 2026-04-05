# mypy: disable-error-code=import-not-found

"""IAM support stack for the AWS-native Nova release control plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aws_cdk import CfnOutput, DefaultStackSynthesizer, Stack, aws_iam as iam
from constructs import Construct

from .runtime_stack import (
    _APPCONFIG_ENVIRONMENT_TAG_KEY,
    _APPCONFIG_MANAGED_BY_TAG_KEY,
    _APPCONFIG_MANAGED_BY_TAG_VALUE,
    _export_copy_worker_dlq_name,
    _export_copy_worker_queue_name,
    _observability_dashboard_name,
    _optional_context_or_env_value,
    _runtime_alarm_names,
    _transfer_spend_budget_name,
)


def _optional_value(scope: Construct, *, key: str, env_var: str) -> str | None:
    raw = _optional_context_or_env_value(scope, key=key, env_var=env_var)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


@dataclass(frozen=True)
class ReleaseSupportInputs:
    """Resolved inputs for the release support IAM stack."""

    dev_role_name: str
    hosted_zone_id: str | None
    prod_role_name: str


def load_release_support_inputs(scope: Construct) -> ReleaseSupportInputs:
    """Resolve release-support role names from context or environment.

    Args:
        scope: Construct scope used to resolve context and environment values.

    Returns:
        Resolved release-support inputs.
    """
    return ReleaseSupportInputs(
        dev_role_name=_optional_value(
            scope,
            key="dev_runtime_cfn_execution_role_name",
            env_var="DEV_RUNTIME_CFN_EXECUTION_ROLE_NAME",
        )
        or "nova-release-dev-cfn-execution",
        hosted_zone_id=_optional_value(
            scope,
            key="hosted_zone_id",
            env_var="HOSTED_ZONE_ID",
        ),
        prod_role_name=_optional_value(
            scope,
            key="prod_runtime_cfn_execution_role_name",
            env_var="PROD_RUNTIME_CFN_EXECUTION_ROLE_NAME",
        )
        or "nova-release-prod-cfn-execution",
    )


class NovaReleaseSupportStack(Stack):
    """Provision CloudFormation execution roles for the release pipeline."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        inputs: ReleaseSupportInputs | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the release-support IAM stack.

        Args:
            scope: Parent construct scope.
            construct_id: CDK construct identifier.
            inputs: Optional release-support role name inputs.
            **kwargs: Additional CDK stack keyword arguments.
        """
        super().__init__(scope, construct_id, **kwargs)

        resolved_inputs = inputs or load_release_support_inputs(self)

        self.dev_cfn_execution_role = self._build_runtime_cfn_execution_role(
            "DevRuntimeCfnExecutionRole",
            deployment_environment="dev",
            hosted_zone_id=resolved_inputs.hosted_zone_id,
            role_name=resolved_inputs.dev_role_name,
        )
        self.prod_cfn_execution_role = self._build_runtime_cfn_execution_role(
            "ProdRuntimeCfnExecutionRole",
            deployment_environment="prod",
            hosted_zone_id=resolved_inputs.hosted_zone_id,
            role_name=resolved_inputs.prod_role_name,
        )

        CfnOutput(
            self,
            "DevRuntimeCfnExecutionRoleArn",
            value=self.dev_cfn_execution_role.role_arn,
        )
        CfnOutput(
            self,
            "ProdRuntimeCfnExecutionRoleArn",
            value=self.prod_cfn_execution_role.role_arn,
        )

    def _build_runtime_cfn_execution_role(
        self,
        construct_id: str,
        *,
        deployment_environment: str,
        hosted_zone_id: str | None,
        role_name: str,
    ) -> iam.Role:
        alarm_names = _runtime_alarm_names(deployment_environment)
        bootstrap_qualifier = (
            self.node.try_get_context("bootstrap_qualifier")
            or DefaultStackSynthesizer.DEFAULT_QUALIFIER
        )
        alarm_topic_name = f"nova-runtime-alarms-{deployment_environment}"
        dashboard_name = _observability_dashboard_name(deployment_environment)
        transfer_budget_name = _transfer_spend_budget_name(
            deployment_environment
        )
        sns_topic_arn = (
            f"arn:{self.partition}:sns:{self.region}:{self.account}:"
            f"{alarm_topic_name}"
        )
        sqs_queue_arns = [
            (
                f"arn:{self.partition}:sqs:{self.region}:{self.account}:"
                f"{_export_copy_worker_queue_name(deployment_environment)}"
            ),
            (
                f"arn:{self.partition}:sqs:{self.region}:{self.account}:"
                f"{_export_copy_worker_dlq_name(deployment_environment)}"
            ),
        ]
        cloudwatch_alarm_arns = [
            (
                f"arn:{self.partition}:cloudwatch:{self.region}:{self.account}:"
                f"alarm:{alarm_name}"
            )
            for alarm_name in alarm_names.values()
        ]
        cloudwatch_dashboard_arn = (
            f"arn:{self.partition}:cloudwatch::{self.account}:"
            f"dashboard/{dashboard_name}"
        )
        budget_arn = (
            f"arn:{self.partition}:budgets::{self.account}:"
            f"budget/{transfer_budget_name}"
        )
        role = iam.Role(
            self,
            construct_id,
            role_name=role_name,
            assumed_by=iam.ServicePrincipal("cloudformation.amazonaws.com"),
            description=(
                "CloudFormation execution role for Nova runtime stack "
                "deployments driven by the release control plane."
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSCloudFormationFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonAPIGatewayAdministrator"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSLambda_FullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSStepFunctionsFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonDynamoDBFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonS3FullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "CloudWatchLogsFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonEventBridgeFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSWAFFullAccess"
                ),
            ],
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:AttachRolePolicy",
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:DeleteRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:GetRole",
                    "iam:GetRolePolicy",
                    "iam:ListAttachedRolePolicies",
                    "iam:ListRolePolicies",
                    "iam:PassRole",
                    "iam:PutRolePolicy",
                    "iam:TagRole",
                    "iam:UntagRole",
                    "iam:UpdateAssumeRolePolicy",
                ],
                resources=[
                    f"arn:{self.partition}:iam::{self.account}:role/Nova*",
                    f"arn:{self.partition}:iam::{self.account}:role/nova-*",
                ],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:CreateServiceLinkedRole"],
                resources=["*"],
                conditions={
                    "StringLike": {
                        "iam:AWSServiceName": [
                            "lambda.amazonaws.com",
                            "states.amazonaws.com",
                            "apigateway.amazonaws.com",
                            "wafv2.amazonaws.com",
                        ]
                    }
                },
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameters"],
                resources=[
                    (
                        f"arn:{self.partition}:ssm:{self.region}:{self.account}:"
                        f"parameter/cdk-bootstrap/{bootstrap_qualifier}/version"
                    )
                ],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "appconfig:CreateApplication",
                    "appconfig:CreateConfigurationProfile",
                    "appconfig:CreateDeploymentStrategy",
                    "appconfig:CreateEnvironment",
                    "appconfig:StartDeployment",
                    "appconfig:TagResource",
                ],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        (
                            f"aws:RequestTag/{_APPCONFIG_MANAGED_BY_TAG_KEY}"
                        ): _APPCONFIG_MANAGED_BY_TAG_VALUE,
                        (
                            f"aws:RequestTag/{_APPCONFIG_ENVIRONMENT_TAG_KEY}"
                        ): deployment_environment,
                    },
                    "ForAllValues:StringEquals": {
                        "aws:TagKeys": [
                            _APPCONFIG_MANAGED_BY_TAG_KEY,
                            _APPCONFIG_ENVIRONMENT_TAG_KEY,
                        ]
                    },
                },
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["appconfig:CreateHostedConfigurationVersion"],
                resources=["*"],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "appconfig:Delete*",
                    "appconfig:Get*",
                    "appconfig:ListTagsForResource",
                    "appconfig:StopDeployment",
                    "appconfig:TagResource",
                    "appconfig:UntagResource",
                    "appconfig:Update*",
                ],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        (
                            f"aws:ResourceTag/{_APPCONFIG_MANAGED_BY_TAG_KEY}"
                        ): _APPCONFIG_MANAGED_BY_TAG_VALUE,
                        (
                            f"aws:ResourceTag/{_APPCONFIG_ENVIRONMENT_TAG_KEY}"
                        ): deployment_environment,
                    }
                },
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["budgets:ModifyBudget", "budgets:ViewBudget"],
                resources=[budget_arn],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "cloudwatch:DeleteAlarms",
                    "cloudwatch:DeleteDashboards",
                    "cloudwatch:GetDashboard",
                    "cloudwatch:PutDashboard",
                    "cloudwatch:PutMetricAlarm",
                ],
                resources=[cloudwatch_dashboard_arn, *cloudwatch_alarm_arns],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "cloudwatch:DescribeAlarms",
                    "cloudwatch:ListDashboards",
                ],
                resources=["*"],
            )
        )
        if hosted_zone_id is not None:
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "route53:ChangeResourceRecordSets",
                        "route53:GetHostedZone",
                        "route53:ListResourceRecordSets",
                    ],
                    resources=[
                        (
                            f"arn:{self.partition}:route53:::hostedzone/"
                            f"{hosted_zone_id}"
                        )
                    ],
                )
            )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["sns:*"],
                resources=[sns_topic_arn],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["sqs:*"],
                resources=sqs_queue_arns,
            )
        )
        return role
