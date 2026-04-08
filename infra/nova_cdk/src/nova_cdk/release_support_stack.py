"""IAM support stack for the AWS-native Nova release control plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from aws_cdk import CfnOutput, DefaultStackSynthesizer, Stack, aws_iam as iam
from constructs import Construct

from .context_inputs import optional_context_or_env_value
from .runtime_naming import (
    APPCONFIG_ENVIRONMENT_TAG_KEY,
    APPCONFIG_MANAGED_BY_TAG_KEY,
    APPCONFIG_MANAGED_BY_TAG_VALUE,
    RESOURCE_ENVIRONMENT_TAG_KEY,
    RESOURCE_OWNER_TAG_KEY,
    RESOURCE_OWNER_TAG_VALUE,
    export_copy_worker_dlq_name,
    export_copy_worker_queue_name,
    export_workflow_log_group_name,
    observability_dashboard_name,
    runtime_alarm_names,
    transfer_spend_budget_name,
)
from .runtime_release_manifest import API_FUNCTION, WORKFLOW_FUNCTIONS


def _optional_value(scope: Construct, *, key: str, env_var: str) -> str | None:
    raw = optional_context_or_env_value(scope, key=key, env_var=env_var)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _create_request_tag_conditions(
    *,
    deployment_environment: str,
) -> dict[str, Any]:
    return {
        "StringEquals": {
            (
                f"aws:RequestTag/{RESOURCE_OWNER_TAG_KEY}"
            ): RESOURCE_OWNER_TAG_VALUE,
            (
                f"aws:RequestTag/{RESOURCE_ENVIRONMENT_TAG_KEY}"
            ): deployment_environment,
        },
        "ForAllValues:StringEquals": {
            "aws:TagKeys": [
                RESOURCE_OWNER_TAG_KEY,
                RESOURCE_ENVIRONMENT_TAG_KEY,
            ]
        },
    }


def _resource_tag_conditions(
    *,
    deployment_environment: str,
) -> dict[str, Any]:
    return {
        "StringEquals": {
            (
                f"aws:ResourceTag/{RESOURCE_OWNER_TAG_KEY}"
            ): RESOURCE_OWNER_TAG_VALUE,
            (
                f"aws:ResourceTag/{RESOURCE_ENVIRONMENT_TAG_KEY}"
            ): deployment_environment,
        }
    }


def _runtime_lambda_function_arns(
    *,
    account: str,
    partition: str,
    region: str,
) -> list[str]:
    """Return wildcard Lambda ARNs for the runtime stack in this account."""
    base_arn = f"arn:{partition}:lambda:{region}:{account}:function:*"
    return [base_arn, f"{base_arn}:*"]


def _runtime_state_machine_arns(
    *,
    account: str,
    partition: str,
    region: str,
) -> list[str]:
    """Return wildcard Step Functions ARNs."""
    base_arn = f"arn:{partition}:states:{region}:{account}:stateMachine:*"
    return [base_arn, f"{base_arn}:*"]


def _runtime_dynamodb_table_arns(
    *,
    account: str,
    partition: str,
    region: str,
) -> list[str]:
    """Return wildcard DynamoDB table ARNs for runtime-managed tables."""
    return [f"arn:{partition}:dynamodb:{region}:{account}:table/*"]


def _runtime_s3_bucket_arns(*, partition: str) -> list[str]:
    """Return wildcard S3 bucket ARNs for runtime-managed buckets."""
    return [f"arn:{partition}:s3:::*", f"arn:{partition}:s3:::*/*"]


def _runtime_logs_arns(
    *,
    account: str,
    partition: str,
    region: str,
    deployment_environment: str,
) -> list[str]:
    """Return deterministic CloudWatch Logs ARNs for runtime log groups."""
    log_group_names = [
        f"{API_FUNCTION.function_name}Logs",
        *(f"{authority.function_name}Logs" for authority in WORKFLOW_FUNCTIONS),
        export_workflow_log_group_name(deployment_environment),
    ]
    return [
        (
            f"arn:{partition}:logs:{region}:{account}:log-group:"
            f"{log_group_name}:*"
        )
        for log_group_name in log_group_names
    ]


def _runtime_events_rule_arns(
    *,
    account: str,
    partition: str,
    region: str,
) -> list[str]:
    """Return wildcard EventBridge rule ARNs for runtime-managed rules."""
    return [f"arn:{partition}:events:{region}:{account}:rule/*"]


def _runtime_wafv2_web_acl_arns(
    *,
    account: str,
    partition: str,
    region: str,
) -> list[str]:
    """Return wildcard WAFv2 Web ACL ARNs for runtime-managed web ACLs."""
    return [f"arn:{partition}:wafv2:{region}:{account}:regional/webacl/*/*"]


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
        alarm_names = runtime_alarm_names(deployment_environment)
        bootstrap_qualifier = (
            self.node.try_get_context("bootstrap_qualifier")
            or DefaultStackSynthesizer.DEFAULT_QUALIFIER
        )
        alarm_topic_name = f"nova-runtime-alarms-{deployment_environment}"
        dashboard_name = observability_dashboard_name(deployment_environment)
        transfer_budget_name = transfer_spend_budget_name(
            deployment_environment
        )
        sns_topic_arn = (
            f"arn:{self.partition}:sns:{self.region}:{self.account}:"
            f"{alarm_topic_name}"
        )
        sqs_queue_arns = [
            (
                f"arn:{self.partition}:sqs:{self.region}:{self.account}:"
                f"{export_copy_worker_queue_name(deployment_environment)}"
            ),
            (
                f"arn:{self.partition}:sqs:{self.region}:{self.account}:"
                f"{export_copy_worker_dlq_name(deployment_environment)}"
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
            assumed_by=cast(
                iam.IPrincipal,
                iam.ServicePrincipal("cloudformation.amazonaws.com"),
            ),
            description=(
                "CloudFormation execution role for Nova runtime stack "
                "deployments driven by the release control plane."
            ),
        )
        lambda_function_arns = _runtime_lambda_function_arns(
            account=self.account,
            partition=self.partition,
            region=self.region,
        )
        state_machine_arns = _runtime_state_machine_arns(
            account=self.account,
            partition=self.partition,
            region=self.region,
        )
        dynamodb_table_arns = _runtime_dynamodb_table_arns(
            account=self.account,
            partition=self.partition,
            region=self.region,
        )
        s3_bucket_arns = _runtime_s3_bucket_arns(partition=self.partition)
        log_group_arns = _runtime_logs_arns(
            account=self.account,
            partition=self.partition,
            region=self.region,
            deployment_environment=deployment_environment,
        )
        event_rule_arns = _runtime_events_rule_arns(
            account=self.account,
            partition=self.partition,
            region=self.region,
        )
        waf_web_acl_arns = _runtime_wafv2_web_acl_arns(
            account=self.account,
            partition=self.partition,
            region=self.region,
        )
        request_tag_conditions = _create_request_tag_conditions(
            deployment_environment=deployment_environment
        )
        resource_tag_conditions = _resource_tag_conditions(
            deployment_environment=deployment_environment
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
                actions=[
                    "apigateway:DELETE",
                    "apigateway:GET",
                    "apigateway:PATCH",
                    "apigateway:POST",
                    "apigateway:PUT",
                    "apigateway:TagResource",
                    "apigateway:UntagResource",
                ],
                resources=["*"],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:CreateEventSourceMapping",
                ],
                resources=["*"],
                conditions=request_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:AddPermission",
                    "lambda:DeleteFunction",
                    "lambda:DeleteFunctionConcurrency",
                    "lambda:GetFunction",
                    "lambda:GetFunctionConfiguration",
                    "lambda:ListTags",
                    "lambda:PublishVersion",
                    "lambda:PutFunctionConcurrency",
                    "lambda:RemovePermission",
                    "lambda:TagResource",
                    "lambda:UntagResource",
                    "lambda:UpdateFunctionCode",
                    "lambda:UpdateFunctionConfiguration",
                ],
                resources=lambda_function_arns,
                conditions=resource_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:CreateFunction",
                ],
                resources=["*"],
                conditions=request_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "states:DeleteStateMachine",
                    "states:DescribeStateMachine",
                    "states:ListTagsForResource",
                    "states:PublishStateMachineVersion",
                    "states:TagResource",
                    "states:UntagResource",
                    "states:UpdateStateMachine",
                ],
                resources=state_machine_arns,
                conditions=resource_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["states:CreateStateMachine"],
                resources=["*"],
                conditions=request_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:DeleteTable",
                    "dynamodb:DescribeContinuousBackups",
                    "dynamodb:DescribeTable",
                    "dynamodb:DescribeTimeToLive",
                    "dynamodb:TagResource",
                    "dynamodb:UntagResource",
                    "dynamodb:UpdateContinuousBackups",
                    "dynamodb:UpdateTable",
                    "dynamodb:UpdateTimeToLive",
                ],
                resources=dynamodb_table_arns,
                conditions=resource_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:CreateTable"],
                resources=["*"],
                conditions=request_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:DeleteBucket",
                    "s3:DeleteBucketTagging",
                    "s3:DeleteStorageLensConfiguration",
                    "s3:GetAccelerateConfiguration",
                    "s3:GetBucketCors",
                    "s3:GetBucketEncryption",
                    "s3:GetBucketLifecycleConfiguration",
                    "s3:GetBucketNotification",
                    "s3:GetBucketPublicAccessBlock",
                    "s3:GetBucketTagging",
                    "s3:GetBucketVersioning",
                    "s3:GetStorageLensConfiguration",
                    "s3:GetStorageLensConfigurationTagging",
                    "s3:PutAccelerateConfiguration",
                    "s3:PutBucketCors",
                    "s3:PutBucketEncryption",
                    "s3:PutBucketLifecycleConfiguration",
                    "s3:PutBucketNotification",
                    "s3:PutBucketPublicAccessBlock",
                    "s3:PutBucketTagging",
                    "s3:PutBucketVersioning",
                    "s3:PutStorageLensConfiguration",
                    "s3:PutStorageLensConfigurationTagging",
                ],
                resources=s3_bucket_arns,
                conditions=resource_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:CreateBucket"],
                resources=["*"],
                conditions=request_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:DeleteLogGroup",
                    "logs:DeleteRetentionPolicy",
                    "logs:DescribeLogGroups",
                    "logs:PutRetentionPolicy",
                    "logs:TagResource",
                    "logs:UntagResource",
                ],
                resources=log_group_arns,
                conditions=resource_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup"],
                resources=["*"],
                conditions=request_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "events:DeleteRule",
                    "events:DescribeRule",
                    "events:DisableRule",
                    "events:EnableRule",
                    "events:ListTargetsByRule",
                    "events:PutTargets",
                    "events:RemoveTargets",
                    "events:TagResource",
                    "events:UntagResource",
                ],
                resources=event_rule_arns,
                conditions=resource_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["events:PutRule"],
                resources=["*"],
                conditions=request_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "wafv2:AssociateWebACL",
                    "wafv2:DeleteLoggingConfiguration",
                    "wafv2:DeleteWebACL",
                    "wafv2:DisassociateWebACL",
                    "wafv2:GetLoggingConfiguration",
                    "wafv2:GetWebACL",
                    "wafv2:ListResourcesForWebACL",
                    "wafv2:ListTagsForResource",
                    "wafv2:PutLoggingConfiguration",
                    "wafv2:TagResource",
                    "wafv2:UntagResource",
                    "wafv2:UpdateWebACL",
                ],
                resources=waf_web_acl_arns,
                conditions=resource_tag_conditions,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["wafv2:CreateWebACL"],
                resources=["*"],
                conditions=request_tag_conditions,
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
                            f"aws:RequestTag/{APPCONFIG_MANAGED_BY_TAG_KEY}"
                        ): APPCONFIG_MANAGED_BY_TAG_VALUE,
                        (
                            f"aws:RequestTag/{RESOURCE_OWNER_TAG_KEY}"
                        ): RESOURCE_OWNER_TAG_VALUE,
                        (
                            f"aws:RequestTag/{APPCONFIG_ENVIRONMENT_TAG_KEY}"
                        ): deployment_environment,
                        (
                            f"aws:RequestTag/{RESOURCE_ENVIRONMENT_TAG_KEY}"
                        ): deployment_environment,
                    },
                    "ForAllValues:StringEquals": {
                        "aws:TagKeys": [
                            APPCONFIG_MANAGED_BY_TAG_KEY,
                            RESOURCE_OWNER_TAG_KEY,
                            APPCONFIG_ENVIRONMENT_TAG_KEY,
                            RESOURCE_ENVIRONMENT_TAG_KEY,
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
                            f"aws:ResourceTag/{APPCONFIG_MANAGED_BY_TAG_KEY}"
                        ): APPCONFIG_MANAGED_BY_TAG_VALUE,
                        (
                            f"aws:ResourceTag/{RESOURCE_OWNER_TAG_KEY}"
                        ): RESOURCE_OWNER_TAG_VALUE,
                        (
                            f"aws:ResourceTag/{APPCONFIG_ENVIRONMENT_TAG_KEY}"
                        ): deployment_environment,
                        (
                            f"aws:ResourceTag/{RESOURCE_ENVIRONMENT_TAG_KEY}"
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
                actions=[
                    "sns:CreateTopic",
                    "sns:DeleteTopic",
                    "sns:GetSubscriptionAttributes",
                    "sns:GetTopicAttributes",
                    "sns:ListSubscriptionsByTopic",
                    "sns:SetSubscriptionAttributes",
                    "sns:SetTopicAttributes",
                    "sns:Subscribe",
                    "sns:TagResource",
                    "sns:Unsubscribe",
                    "sns:UntagResource",
                ],
                resources=[sns_topic_arn],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["sns:ListTopics"],
                resources=["*"],
            )
        )
        sqs_queue_names = [
            queue_arn.rsplit(":", maxsplit=1)[-1]
            for queue_arn in sqs_queue_arns
        ]
        for queue_name in sqs_queue_names:
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=["sqs:CreateQueue"],
                    resources=["*"],
                    conditions={"StringEquals": {"sqs:QueueName": queue_name}},
                )
            )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["sqs:ListQueues"],
                resources=["*"],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:AddPermission",
                    "sqs:ChangeMessageVisibility",
                    "sqs:DeleteMessage",
                    "sqs:DeleteQueue",
                    "sqs:GetQueueAttributes",
                    "sqs:GetQueueUrl",
                    "sqs:ListQueueTags",
                    "sqs:PurgeQueue",
                    "sqs:ReceiveMessage",
                    "sqs:RemovePermission",
                    "sqs:SendMessage",
                    "sqs:SetQueueAttributes",
                    "sqs:TagQueue",
                    "sqs:UntagQueue",
                ],
                resources=sqs_queue_arns,
            )
        )
        return role
