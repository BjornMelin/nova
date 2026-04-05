"""Contract tests for the release-support IAM stack."""

from __future__ import annotations

import json

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

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
    template = _template()

    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "ManagedPolicyArns": Match.array_with(
                [
                    {
                        "Fn::Join": Match.any_value(),
                    }
                ]
            )
        },
    )
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Action": Match.array_with(
                                    [
                                        "iam:CreateRole",
                                        "iam:PassRole",
                                        "iam:PutRolePolicy",
                                    ]
                                ),
                                "Resource": Match.any_value(),
                            }
                        ),
                        Match.object_like(
                            {
                                "Action": "iam:CreateServiceLinkedRole",
                            }
                        ),
                        Match.object_like(
                            {
                                "Action": "ssm:GetParameters",
                                "Resource": {
                                    "Fn::Join": Match.array_with(
                                        [
                                            Match.array_with(
                                                [
                                                    "arn:",
                                                    {"Ref": "AWS::Partition"},
                                                    ":ssm:us-east-1:111111111111:parameter/cdk-bootstrap/hnb659fds/version",
                                                ]
                                            )
                                        ]
                                    )
                                },
                            }
                        ),
                    ]
                )
            }
        },
    )


def test_release_support_stack_includes_runtime_service_permissions() -> None:
    template_json = json.dumps(_template().to_json(), sort_keys=True)

    assert "parameter/cdk-bootstrap/hnb659fds/version" in template_json
    assert "ssm:GetParameters" in template_json
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
