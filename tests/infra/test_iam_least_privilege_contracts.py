# mypy: disable-error-code=import-not-found

"""Least-privilege contract tests for workflow task IAM."""

from __future__ import annotations

import json
from typing import Any, cast

from .helpers import (
    resources_of_type,
    runtime_stack_template_json,
)


def _policy_document_for_prefix(
    resources: dict[str, Any],
    *,
    prefix: str,
) -> dict[str, Any]:
    """Return the inline policy document for one logical-id prefix."""
    policies = resources_of_type(resources, "AWS::IAM::Policy")
    match = next(
        (
            resource
            for logical_id, resource in policies.items()
            if logical_id.startswith(prefix)
        ),
        None,
    )
    assert match is not None, f"No policy found with prefix '{prefix}'"
    return cast(dict[str, Any], match["Properties"]["PolicyDocument"])


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
    resources = runtime_stack_template_json(stack_name="IamContractStack")[
        "Resources"
    ]
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
    resources = runtime_stack_template_json(stack_name="IamContractStackCopy")[
        "Resources"
    ]
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
    resources = runtime_stack_template_json(
        stack_name="IamContractStackWorkflowEnv"
    )["Resources"]
    functions = resources_of_type(resources, "AWS::Lambda::Function")
    workflow_functions = [
        resource["Properties"]
        for logical_id, resource in functions.items()
        if logical_id.startswith(
            (
                "ValidateExportFunction",
                "CopyExportFunction",
                "FinalizeExportFunction",
                "FailExportFunction",
            )
        )
    ]
    assert workflow_functions
    for props in workflow_functions:
        env = props["Environment"]["Variables"]
        assert "ACTIVITY_ROLLUPS_TABLE" not in env
        assert "ACTIVITY_STORE_BACKEND" not in env
