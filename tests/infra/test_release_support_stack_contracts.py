"""Contract tests for the release-support IAM stack."""

from __future__ import annotations

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

from .helpers import load_repo_package_module, resources_of_type

_STACK_MODULE = load_repo_package_module(
    "nova_cdk.release_support_stack",
    "infra/nova_cdk/src",
)
NovaReleaseSupportStack = _STACK_MODULE.NovaReleaseSupportStack


def _template() -> Template:
    app = App()
    stack = NovaReleaseSupportStack(
        app,
        "ReleaseSupportContractStack",
        env=Environment(account="111111111111", region="us-east-1"),
    )
    return Template.from_stack(stack)


def test_release_support_stack_synthesizes_two_cfn_execution_roles() -> None:
    template = _template().to_json()
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
                    ]
                )
            }
        },
    )
