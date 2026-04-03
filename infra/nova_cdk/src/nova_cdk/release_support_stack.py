# mypy: disable-error-code=import-not-found

"""IAM support stack for the AWS-native Nova release control plane."""

from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import CfnOutput, Stack, aws_iam as iam
from constructs import Construct

from .runtime_stack import _optional_context_or_env_value


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
    prod_role_name: str


def load_release_support_inputs(scope: Construct) -> ReleaseSupportInputs:
    """Resolve release-support role names from context or environment."""
    return ReleaseSupportInputs(
        dev_role_name=_optional_value(
            scope,
            key="dev_runtime_cfn_execution_role_name",
            env_var="DEV_RUNTIME_CFN_EXECUTION_ROLE_NAME",
        )
        or "nova-release-dev-cfn-execution",
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
        **kwargs: object,
    ) -> None:
        """Initialize the release-support IAM stack."""
        super().__init__(scope, construct_id, **kwargs)

        resolved_inputs = inputs or load_release_support_inputs(self)

        self.dev_cfn_execution_role = self._build_runtime_cfn_execution_role(
            "DevRuntimeCfnExecutionRole",
            role_name=resolved_inputs.dev_role_name,
        )
        self.prod_cfn_execution_role = self._build_runtime_cfn_execution_role(
            "ProdRuntimeCfnExecutionRole",
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
        role_name: str,
    ) -> iam.Role:
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
                    "PowerUserAccess"
                )
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
                resources=[f"arn:{self.partition}:iam::{self.account}:role/*"],
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
        return role
