"""Contract tests for the release-support IAM stack."""

from __future__ import annotations

import json

from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from .helpers import load_repo_package_module, resources_of_type

_STACK_MODULE = load_repo_package_module(
    "nova_cdk.release_support_stack",
    "infra/nova_cdk/src",
)
NovaReleaseSupportStack = _STACK_MODULE.NovaReleaseSupportStack


def _template(*, hosted_zone_id: str | None = "Z1234567890EXAMPLE") -> Template:
    context = (
        {"hosted_zone_id": hosted_zone_id}
        if hosted_zone_id is not None
        else None
    )
    app = App(context=context)
    stack = NovaReleaseSupportStack(
        app,
        "ReleaseSupportContractStack",
        env=Environment(account="111111111111", region="us-east-1"),
    )
    return Template.from_stack(stack)


def test_release_support_stack_synthesizes_two_cfn_execution_roles() -> None:
    template = _template(hosted_zone_id=None).to_json()
    roles = resources_of_type(template["Resources"], "AWS::IAM::Role")

    assert len(roles) == 2
    for role in roles.values():
        statements = role["Properties"]["AssumeRolePolicyDocument"]["Statement"]
        assert statements == [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": "cloudformation.amazonaws.com"},
            }
        ]


def test_release_support_stack_attaches_inline_iam_controls() -> None:
    template_json = _template().to_json()
    roles = resources_of_type(template_json["Resources"], "AWS::IAM::Role")
    assert roles
    for role in roles.values():
        assert "ManagedPolicyArns" not in role["Properties"]
    policy_text = json.dumps(template_json, sort_keys=True)
    assert '"iam:CreateRole"' in policy_text
    assert '"iam:PassRole"' in policy_text
    assert '"iam:PutRolePolicy"' in policy_text
    assert '"apigateway:DELETE"' in policy_text
    assert '"apigateway:GET"' in policy_text
    assert '"lambda:CreateFunction"' in policy_text
    assert '"lambda:UpdateFunctionConfiguration"' in policy_text
    assert '"lambda:UpdateFunctionCode"' in policy_text
    assert '"states:CreateStateMachine"' in policy_text
    assert '"states:UpdateStateMachine"' in policy_text
    assert '"states:DeleteStateMachine"' in policy_text
    assert '"iam:CreateServiceLinkedRole"' in policy_text
    assert '"ssm:GetParameters"' in policy_text
    assert "parameter/cdk-bootstrap/hnb659fds/version" in policy_text


def test_release_support_stack_includes_runtime_service_permissions() -> None:
    template_json = json.dumps(_template().to_json(), sort_keys=True)

    assert "parameter/cdk-bootstrap/hnb659fds/version" in template_json
    assert "ssm:GetParameters" in template_json
    assert "apigateway:DELETE" in template_json
    assert "lambda:CreateFunction" in template_json
    assert "lambda:UpdateFunctionCode" in template_json
    assert "states:CreateStateMachine" in template_json
    assert "dynamodb:CreateTable" in template_json
    assert "s3:PutStorageLensConfiguration" in template_json
    assert "logs:PutRetentionPolicy" in template_json
    assert "events:PutRule" in template_json
    assert "wafv2:CreateWebACL" in template_json
    assert "appconfig:CreateApplication" in template_json
    assert "appconfig:Update*" in template_json
    assert "aws:RequestTag/NovaManagedBy" in template_json
    assert "aws:ResourceTag/NovaDeploymentEnvironment" in template_json
    assert "budget/nova-transfer-dev" in template_json
    assert "nova-runtime-alarms-dev" in template_json
    assert "nova-export-copy-worker-dev" in template_json
    assert "hostedzone/Z1234567890EXAMPLE" in template_json
    assert (
        ":cloudwatch::111111111111:dashboard/nova-runtime-observability-dev"
    ) in template_json
    assert (
        ":cloudwatch:us-east-1:111111111111:"
        "dashboard/nova-runtime-observability-dev"
    ) not in template_json
    assert "alarm:nova-dev-api-lambda-errors" in template_json
    assert '"Action": "appconfig:*"' not in template_json
    assert '"Action": "budgets:*"' not in template_json
    assert '"Action": "cloudwatch:*"' not in template_json
    assert '"Action": "route53:*"' not in template_json
    assert '"sns:*"' not in template_json
    assert '"sqs:*"' not in template_json
    assert "AWSCloudFormationFullAccess" not in template_json
    assert "AmazonAPIGatewayAdministrator" not in template_json
    assert "AWSLambda_FullAccess" not in template_json
    assert "AWSStepFunctionsFullAccess" not in template_json
    assert "AmazonDynamoDBFullAccess" not in template_json
    assert "AmazonS3FullAccess" not in template_json
    assert "CloudWatchLogsFullAccess" not in template_json
    assert "AmazonEventBridgeFullAccess" not in template_json
    assert "AWSWAFFullAccess" not in template_json


def test_release_support_stack_synthesizes_without_hosted_zone_input() -> None:
    template_json = json.dumps(
        _template(hosted_zone_id=None).to_json(),
        sort_keys=True,
    )

    assert "nova-release-dev-cfn-execution" in template_json
    assert "nova-release-prod-cfn-execution" in template_json
    assert "dashboard/nova-runtime-observability-dev" in template_json
    assert "hostedzone/" not in template_json
    assert "route53:ChangeResourceRecordSets" not in template_json
