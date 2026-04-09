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


def _statement_actions(statement: dict[str, Any]) -> set[str]:
    raw_actions = statement.get("Action")
    if isinstance(raw_actions, list):
        return {cast(str, action) for action in raw_actions}
    if isinstance(raw_actions, str):
        return {raw_actions}
    return set()


def _statement_resources(statement: dict[str, Any]) -> set[str]:
    raw_resources = statement.get("Resource")
    if isinstance(raw_resources, list):
        return {cast(str, resource) for resource in raw_resources}
    if isinstance(raw_resources, str):
        return {raw_resources}
    if isinstance(raw_resources, dict):
        return {json.dumps(raw_resources, sort_keys=True)}
    return set()


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
    """Inline copy role: narrow S3 prefixes plus cancelled-copy cleanup."""
    resources = runtime_stack_template_json(stack_name="IamContractStackCopy")[
        "Resources"
    ]
    policy_document = _policy_document_for_prefix(
        resources,
        prefix="CopyExportFunctionServiceRoleDefaultPolicy",
    )
    statements = cast(list[dict[str, Any]], policy_document["Statement"])
    rendered = json.dumps(policy_document, sort_keys=True)
    assert "ActivityTable" not in rendered
    delete_statements = [
        statement
        for statement in statements
        if any(
            action.startswith("s3:DeleteObject")
            for action in _statement_actions(statement)
        )
    ]
    assert delete_statements
    assert any(
        any(
            "exports/*" in resource
            for resource in _statement_resources(statement)
        )
        for statement in delete_statements
    )
    assert all(
        not any(
            resource == "*" or "uploads/*" in resource
            for resource in _statement_resources(statement)
        )
        for statement in delete_statements
    )
    assert "uploads/*" in rendered
    assert "exports/*" in rendered
    assert "BatchWriteItem" not in rendered
    assert "Query" not in rendered
    assert "Scan" not in rendered


def test_non_inline_copy_workflow_roles_do_not_gain_delete_access() -> None:
    """Queued-copy roles should keep copy-only export-prefix access."""
    resources = runtime_stack_template_json(
        stack_name="IamContractStackQueuedCopy"
    )["Resources"]
    for prefix in (
        "PrepareExportCopyFunctionServiceRoleDefaultPolicy",
        "StartQueuedExportCopyFunctionServiceRoleDefaultPolicy",
        "PollQueuedExportCopyFunctionServiceRoleDefaultPolicy",
        "ExportCopyWorkerFunctionServiceRoleDefaultPolicy",
    ):
        policy_document = _policy_document_for_prefix(resources, prefix=prefix)
        rendered = json.dumps(policy_document, sort_keys=True)
        assert "DeleteObject" not in rendered


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
