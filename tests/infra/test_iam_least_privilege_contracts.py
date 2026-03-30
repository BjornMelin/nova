# mypy: disable-error-code=import-not-found

"""Least-privilege contract tests for workflow task IAM."""

from __future__ import annotations

import json
from typing import Any, cast

from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from .helpers import load_repo_package_module

_RUNTIME_STACK_MODULE = load_repo_package_module(
    "nova_cdk.runtime_stack",
    "infra/nova_cdk/src",
)
NovaRuntimeStack = _RUNTIME_STACK_MODULE.NovaRuntimeStack


def _context_for_region(region: str) -> dict[str, str]:
    """Return the minimum valid stack context for one region."""
    return {
        "api_domain_name": "api.dev.example.com",
        "api_lambda_artifact_bucket": (
            "nova-ci-artifacts-111111111111-us-east-1"
        ),
        "api_lambda_artifact_key": (
            "runtime/nova-file-api/"
            "01234567-89ab-cdef-0123-456789abcdef/"
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef/"
            "nova-file-api-lambda.zip"
        ),
        "api_lambda_artifact_sha256": (
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
        "certificate_arn": (
            f"arn:aws:acm:{region}:111111111111:"
            "certificate/12345678-1234-1234-1234-123456789012"
        ),
        "hosted_zone_id": "Z1234567890EXAMPLE",
        "hosted_zone_name": "example.com",
        "jwt_audience": "api://nova",
        "jwt_issuer": "https://issuer.example.com/",
        "jwt_jwks_url": "https://issuer.example.com/.well-known/jwks.json",
    }


def _template_json(
    *,
    context: dict[str, str] | None = None,
    region: str = "us-west-2",
) -> dict[str, Any]:
    """Return the synthesized template JSON for one stack context."""
    app = App(context=context or _context_for_region(region))
    stack = NovaRuntimeStack(
        app,
        "IamContractStack",
        env=Environment(account="111111111111", region=region),
    )
    return cast(dict[str, Any], Template.from_stack(stack).to_json())


def _resources_of_type(
    resources: dict[str, Any],
    type_name: str,
) -> dict[str, dict[str, Any]]:
    """Return all template resources of one CloudFormation type."""
    return {
        logical_id: resource
        for logical_id, resource in resources.items()
        if resource["Type"] == type_name
    }


def _policy_document_for_prefix(
    resources: dict[str, Any],
    *,
    prefix: str,
) -> dict[str, Any]:
    """Return the inline policy document for one logical-id prefix."""
    policies = _resources_of_type(resources, "AWS::IAM::Policy")
    logical_id, resource = next(
        (logical_id, resource)
        for logical_id, resource in policies.items()
        if logical_id.startswith(prefix)
    )
    del logical_id
    return cast(dict[str, Any], resource["Properties"]["PolicyDocument"])


def _all_actions(policy_document: dict[str, Any]) -> set[str]:
    """Return every action mentioned across one IAM policy document."""
    actions: set[str] = set()
    for statement in policy_document["Statement"]:
        raw_actions = statement["Action"]
        if isinstance(raw_actions, list):
            actions.update(cast(list[str], raw_actions))
        else:
            actions.add(cast(str, raw_actions))
    return actions


def test_status_only_workflow_roles_do_not_keep_s3_or_activity_access() -> None:
    """Validate/finalize/fail roles: DynamoDB export status only."""
    resources = _template_json()["Resources"]
    allowed_actions = {
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "xray:PutTelemetryRecords",
        "xray:PutTraceSegments",
    }
    for prefix in (
        "ValidateExportFunctionServiceRoleDefaultPolicy",
        "FinalizeExportFunctionServiceRoleDefaultPolicy",
        "FailExportFunctionServiceRoleDefaultPolicy",
    ):
        policy_document = _policy_document_for_prefix(
            resources,
            prefix=prefix,
        )
        rendered = json.dumps(policy_document, sort_keys=True)
        assert "ActivityTable" not in rendered
        assert "s3:" not in rendered
        assert _all_actions(policy_document) <= allowed_actions


def test_copy_workflow_role_is_scoped_to_upload_and_export_prefixes() -> None:
    """Copy role: narrow S3 prefixes only; no activity table."""
    resources = _template_json()["Resources"]
    policy_document = _policy_document_for_prefix(
        resources,
        prefix="CopyExportFunctionServiceRoleDefaultPolicy",
    )
    rendered = json.dumps(policy_document, sort_keys=True)

    assert "ActivityTable" not in rendered
    assert "uploads/*" in rendered
    assert "exports/*" in rendered
    assert "DeleteObject" not in rendered
    assert "BatchWriteItem" not in rendered
    assert "Query" not in rendered
    assert "Scan" not in rendered


def test_workflow_lambdas_drop_unused_activity_env() -> None:
    """Workflow task Lambdas should not carry unused activity-store settings."""
    resources = _template_json()["Resources"]
    functions = _resources_of_type(resources, "AWS::Lambda::Function")
    workflow_functions = [
        resource["Properties"]
        for logical_id, resource in functions.items()
        if logical_id != "NovaApiFunctionF531316A"
    ]
    assert workflow_functions
    for props in workflow_functions:
        env = props["Environment"]["Variables"]
        assert "ACTIVITY_ROLLUPS_TABLE" not in env
        assert "ACTIVITY_STORE_BACKEND" not in env
