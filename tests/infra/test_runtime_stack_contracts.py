# mypy: disable-error-code=import-not-found

"""Contract tests for the canonical Nova runtime CDK stack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
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
        "workflow_lambda_artifact_bucket": (
            "nova-ci-artifacts-111111111111-us-east-1"
        ),
        "workflow_lambda_artifact_key": (
            "runtime/nova-workflows/"
            "01234567-89ab-cdef-0123-456789abcdef/"
            "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210/"
            "nova-workflows-lambda.zip"
        ),
        "workflow_lambda_artifact_sha256": (
            "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
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


@dataclass(frozen=True)
class _TemplateBundle:
    """Hold the template fragments used by runtime contract tests."""

    api_function_env: dict[str, str]
    definition_fragment: str
    outputs: dict[str, Any]
    resources: dict[str, Any]


def _template(
    *,
    context: dict[str, str] | None = None,
    region: str = "us-west-2",
) -> Template:
    """Synthesize the runtime stack to a template for assertions."""
    app = App(context=context or _context_for_region(region))
    stack = NovaRuntimeStack(
        app,
        "RuntimeContractStack",
        env=Environment(account="111111111111", region=region),
    )
    return Template.from_stack(stack)


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


def _api_function_env(resources: dict[str, Any]) -> dict[str, str]:
    """Return the API Lambda environment block from the synthesized template."""
    functions = _resources_of_type(resources, "AWS::Lambda::Function")
    for resource in functions.values():
        variables = (
            resource["Properties"].get("Environment", {}).get("Variables")
        )
        if isinstance(variables, dict) and (
            "EXPORT_WORKFLOW_STATE_MACHINE_ARN" in variables
        ):
            return variables
    raise AssertionError("Could not locate the API Lambda environment block")


def _workflow_function_resources(
    resources: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return workflow Lambda resources keyed by logical id."""
    functions = _resources_of_type(resources, "AWS::Lambda::Function")
    return {
        logical_id: resource
        for logical_id, resource in functions.items()
        if logical_id.startswith(
            (
                "ValidateExportFunction",
                "CopyExportFunction",
                "FinalizeExportFunction",
                "FailExportFunction",
            )
        )
    }


def _definition_fragment(resources: dict[str, Any]) -> str:
    """Return the rendered Step Functions JSON fragment for assertions."""
    state_machines = _resources_of_type(
        resources,
        "AWS::StepFunctions::StateMachine",
    )
    assert len(state_machines) == 1
    resource = next(iter(state_machines.values()))
    return "".join(
        part
        for part in resource["Properties"]["DefinitionString"]["Fn::Join"][1]
        if isinstance(part, str)
    )


def _build_bundle(
    *,
    context: dict[str, str] | None = None,
    region: str = "us-west-2",
) -> _TemplateBundle:
    """Build a reusable template bundle for runtime assertions."""
    template_json = _template(context=context, region=region).to_json()
    resources = template_json["Resources"]
    return _TemplateBundle(
        api_function_env=_api_function_env(resources),
        definition_fragment=_definition_fragment(resources),
        outputs=template_json["Outputs"],
        resources=resources,
    )


@pytest.mark.parametrize(
    "missing_key",
    [
        "api_domain_name",
        "api_lambda_artifact_bucket",
        "api_lambda_artifact_key",
        "api_lambda_artifact_sha256",
        "workflow_lambda_artifact_bucket",
        "workflow_lambda_artifact_key",
        "workflow_lambda_artifact_sha256",
        "certificate_arn",
        "hosted_zone_id",
        "hosted_zone_name",
        "jwt_audience",
        "jwt_issuer",
        "jwt_jwks_url",
    ],
)
def test_runtime_stack_requires_complete_context(missing_key: str) -> None:
    """Runtime synth must fail closed on incomplete stack inputs."""
    context = _context_for_region("us-west-2")
    context.pop(missing_key)

    with pytest.raises(ValueError, match=missing_key):
        _template(context=context)


def test_runtime_stack_passes_oidc_env_to_api_lambda() -> None:
    """API Lambda must receive the in-process OIDC verifier settings."""
    bundle = _build_bundle()
    api_function_env = bundle.api_function_env
    assert api_function_env["OIDC_ISSUER"] == "https://issuer.example.com/"
    assert api_function_env["OIDC_AUDIENCE"] == "api://nova"
    assert (
        api_function_env["OIDC_JWKS_URL"]
        == "https://issuer.example.com/.well-known/jwks.json"
    )


def test_runtime_stack_maps_caught_errors_for_failure_handler() -> None:
    """Route workflow failure fields to the fail handler input payload."""
    bundle = _build_bundle()
    definition_fragment = bundle.definition_fragment
    assert "$.workflow_error.Error" in definition_fragment
    assert "$.workflow_error.Cause" in definition_fragment
    assert "$.workflow_error" in definition_fragment
    assert '"status":"failed"' in definition_fragment
    assert '"updated_at.$":"$.updated_at"' in definition_fragment
    assert '"JitterStrategy":"FULL"' in definition_fragment
    assert '"MaxDelaySeconds":30' in definition_fragment
    assert '"Lambda.TooManyRequestsException"' in definition_fragment
    assert '"States.Timeout"' in definition_fragment


def test_runtime_stack_packages_api_lambda_as_native_zip() -> None:
    """API Lambda should use zip packaging and the repo-owned entrypoint."""
    bundle = _build_bundle()
    functions = _resources_of_type(bundle.resources, "AWS::Lambda::Function")
    api_resource = next(
        resource
        for resource in functions.values()
        if (
            resource["Properties"]
            .get("Environment", {})
            .get("Variables", {})
            .get("EXPORT_WORKFLOW_STATE_MACHINE_ARN")
        )
    )
    props = api_resource["Properties"]
    assert props["Handler"] == "nova_file_api.lambda_handler.handler"
    assert props["Runtime"] == "python3.13"
    assert props["ReservedConcurrentExecutions"] == 5
    assert "S3Bucket" in props["Code"]
    assert (
        props["Code"]["S3Key"]
        == _context_for_region("us-west-2")["api_lambda_artifact_key"]
    )
    assert "ImageUri" not in props.get("Code", {})
    assert (
        props["Environment"]["Variables"]["API_RELEASE_ARTIFACT_SHA256"]
        == _context_for_region("us-west-2")["api_lambda_artifact_sha256"]
    )
    assert (
        "FILE_TRANSFER_UPLOAD_SESSIONS_TABLE"
        in props["Environment"]["Variables"]
    )
    assert props["Environment"]["Variables"][
        "FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES"
    ] == str(2 * 1024 * 1024 * 1024)
    assert props["Environment"]["Variables"][
        "FILE_TRANSFER_LARGE_EXPORT_WORKER_THRESHOLD_BYTES"
    ] == str(50 * 1024 * 1024 * 1024)
    assert (
        props["Environment"]["Variables"][
            "FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY"
        ]
        == "8"
    )
    assert (
        props["Environment"]["Variables"]["FILE_TRANSFER_CHECKSUM_MODE"]
        == "none"
    )
    assert props["Environment"]["Variables"]["FILE_TRANSFER_POLICY_ID"] == (
        "default"
    )

    policies = _resources_of_type(bundle.resources, "AWS::IAM::Policy")
    policy_fragments = [
        str(resource["Properties"]["PolicyDocument"])
        for resource in policies.values()
    ]
    assert any(
        "states:DescribeStateMachine" in fragment
        for fragment in policy_fragments
    )
    assert any(
        "states:StopExecution" in fragment for fragment in policy_fragments
    )
    assert any(
        ":execution/" in fragment and "ExportWorkflowStateMachine" in fragment
        for fragment in policy_fragments
    )
    assert any(
        "appconfig:StartConfigurationSession" in fragment
        and "appconfig:GetLatestConfiguration" in fragment
        for fragment in policy_fragments
    )

    workflow_resources = [
        resource
        for resource in functions.values()
        if resource["Properties"]["Handler"]
        == "nova_workflows.handlers.copy_export_handler"
    ]
    assert len(workflow_resources) == 1
    workflow_env = workflow_resources[0]["Properties"]["Environment"][
        "Variables"
    ]
    assert workflow_env["FILE_TRANSFER_EXPORT_COPY_PART_SIZE_BYTES"] == str(
        2 * 1024 * 1024 * 1024
    )
    assert workflow_env["FILE_TRANSFER_EXPORT_COPY_MAX_CONCURRENCY"] == "8"
    assert workflow_env["FILE_TRANSFER_EXPORT_COPY_WORKER_ATTEMPTS"] == "5"
    assert workflow_env["FILE_TRANSFER_EXPORT_COPY_QUEUE_URL"]
    assert workflow_env["FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE"]


def test_runtime_stack_adds_upload_session_table_with_upload_index() -> None:
    """Runtime stack should provision durable upload-session storage."""
    bundle = _build_bundle()
    tables = _resources_of_type(bundle.resources, "AWS::DynamoDB::Table")
    upload_session_tables = [
        resource
        for logical_id, resource in tables.items()
        if logical_id.startswith("UploadSessionsTable")
    ]
    assert len(upload_session_tables) == 1
    table = upload_session_tables[0]["Properties"]
    assert table["KeySchema"] == [
        {"AttributeName": "session_id", "KeyType": "HASH"}
    ]
    assert table["TimeToLiveSpecification"] == {
        "AttributeName": "resumable_until_epoch",
        "Enabled": True,
    }
    global_indexes = table["GlobalSecondaryIndexes"]
    assert {
        "IndexName": "upload_id-index",
        "KeySchema": [{"AttributeName": "upload_id", "KeyType": "HASH"}],
        "Projection": {"ProjectionType": "ALL"},
    } in global_indexes
    alarms = _resources_of_type(bundle.resources, "AWS::CloudWatch::Alarm")
    assert any(
        logical_id.startswith("UploadSessionsTableThrottlesAlarm")
        for logical_id in alarms
    )


def test_runtime_stack_adds_transfer_usage_and_policy_resources() -> None:
    """Runtime stack should provision transfer quota and policy resources."""
    bundle = _build_bundle()
    tables = _resources_of_type(bundle.resources, "AWS::DynamoDB::Table")
    usage_tables = [
        resource
        for logical_id, resource in tables.items()
        if logical_id.startswith("TransferUsageTable")
    ]
    assert len(usage_tables) == 1
    table = usage_tables[0]["Properties"]
    assert table["KeySchema"] == [
        {"AttributeName": "scope_id", "KeyType": "HASH"},
        {"AttributeName": "window_key", "KeyType": "RANGE"},
    ]
    assert table["TimeToLiveSpecification"] == {
        "AttributeName": "expires_at",
        "Enabled": True,
    }
    appconfig_resources = _resources_of_type(
        bundle.resources,
        "AWS::AppConfig::Application",
    )
    assert appconfig_resources
    assert _resources_of_type(
        bundle.resources,
        "AWS::AppConfig::ConfigurationProfile",
    )
    assert _resources_of_type(
        bundle.resources,
        "AWS::AppConfig::HostedConfigurationVersion",
    )
    assert _resources_of_type(bundle.resources, "AWS::AppConfig::Deployment")
    api_function_env = bundle.api_function_env
    assert "FILE_TRANSFER_USAGE_TABLE" in api_function_env
    assert "FILE_TRANSFER_POLICY_APPCONFIG_APPLICATION" in api_function_env
    assert "FILE_TRANSFER_POLICY_APPCONFIG_ENVIRONMENT" in api_function_env
    assert "FILE_TRANSFER_POLICY_APPCONFIG_PROFILE" in api_function_env


def test_runtime_stack_adds_export_copy_worker_resources() -> None:
    """Runtime stack should provision queued export-copy resources."""
    bundle = _build_bundle()
    tables = _resources_of_type(bundle.resources, "AWS::DynamoDB::Table")
    assert any(
        logical_id.startswith("ExportCopyPartsTable") for logical_id in tables
    )
    export_copy_tables = [
        resource
        for logical_id, resource in tables.items()
        if logical_id.startswith("ExportCopyPartsTable")
    ]
    assert len(export_copy_tables) == 1
    assert export_copy_tables[0]["Properties"]["TimeToLiveSpecification"] == {
        "AttributeName": "expires_at_epoch",
        "Enabled": True,
    }
    queues = _resources_of_type(bundle.resources, "AWS::SQS::Queue")
    assert any(
        logical_id.startswith("ExportCopyWorkerQueue") for logical_id in queues
    )
    assert any(
        logical_id.startswith("ExportCopyWorkerDlq") for logical_id in queues
    )
    functions = _resources_of_type(bundle.resources, "AWS::Lambda::Function")
    handlers = {
        resource["Properties"]["Handler"] for resource in functions.values()
    }
    assert "nova_workflows.handlers.prepare_export_copy_handler" in handlers
    assert (
        "nova_workflows.handlers.start_queued_export_copy_handler" in handlers
    )
    assert "nova_workflows.handlers.poll_queued_export_copy_handler" in handlers
    assert "nova_workflows.handlers.export_copy_worker_handler" in handlers
    event_sources = _resources_of_type(
        bundle.resources,
        "AWS::Lambda::EventSourceMapping",
    )
    assert any(
        resource["Properties"].get("FunctionResponseTypes")
        == ["ReportBatchItemFailures"]
        for resource in event_sources.values()
    )
    worker_functions = [
        resource
        for resource in functions.values()
        if resource["Properties"]["Handler"]
        == "nova_workflows.handlers.export_copy_worker_handler"
    ]
    assert len(worker_functions) == 1
    worker_env = worker_functions[0]["Properties"]["Environment"]["Variables"]
    assert "FILE_TRANSFER_EXPORT_COPY_PARTS_TABLE" in worker_env
    assert "FILE_TRANSFER_EXPORT_COPY_QUEUE_URL" in worker_env
    assert "FILE_TRANSFER_EXPORT_COPY_WORKER_LEASE_SECONDS" in worker_env
    alarms = _resources_of_type(bundle.resources, "AWS::CloudWatch::Alarm")
    assert any(
        logical_id.startswith("ExportCopyWorkerDlqAlarm")
        for logical_id in alarms
    )
    assert any(
        logical_id.startswith("ExportCopyWorkerQueueAgeAlarm")
        for logical_id in alarms
    )


def test_runtime_stack_adds_transfer_reconciliation_and_cost_controls() -> None:
    """Runtime stack should wire janitor, Storage Lens, and budget controls."""
    bundle = _build_bundle()
    functions = _resources_of_type(bundle.resources, "AWS::Lambda::Function")
    reconcile_functions = [
        resource
        for resource in functions.values()
        if resource["Properties"]["Handler"]
        == "nova_workflows.handlers.reconcile_transfer_state_handler"
    ]
    assert len(reconcile_functions) == 1
    rules = _resources_of_type(bundle.resources, "AWS::Events::Rule")
    assert any(
        logical_id.startswith("TransferReconciliationSchedule")
        for logical_id in rules
    )
    assert _resources_of_type(bundle.resources, "AWS::S3::StorageLens")
    assert _resources_of_type(bundle.resources, "AWS::Budgets::Budget")
    alarms = _resources_of_type(bundle.resources, "AWS::CloudWatch::Alarm")
    assert any(
        logical_id.startswith("StaleMultipartUploadBytesAlarm")
        for logical_id in alarms
    )
    assert any(
        logical_id.startswith("ExportCopyWorkerDlqAlarm")
        for logical_id in alarms
    )
    buckets = _resources_of_type(bundle.resources, "AWS::S3::Bucket")
    file_transfer_buckets = [
        resource
        for logical_id, resource in buckets.items()
        if logical_id.startswith("FileTransferBucket")
    ]
    assert len(file_transfer_buckets) == 1
    assert file_transfer_buckets[0]["Properties"][
        "AccelerateConfiguration"
    ] == {"AccelerationStatus": "Enabled"}


def test_non_prod_can_disable_reserved_concurrency() -> None:
    """Non-prod stacks may omit reservations in low-quota accounts."""
    context = {
        **_context_for_region("us-west-2"),
        "enable_reserved_concurrency": "false",
    }
    bundle = _build_bundle(context=context)
    functions = _resources_of_type(bundle.resources, "AWS::Lambda::Function")
    for resource in functions.values():
        assert "ReservedConcurrentExecutions" not in resource["Properties"]


def test_non_prod_disables_waf_by_default() -> None:
    """Non-prod stacks should skip WAF unless explicitly enabled."""
    bundle = _build_bundle()

    assert "ExportNovaWafLogGroupName" not in bundle.outputs
    assert not _resources_of_type(bundle.resources, "AWS::WAFv2::WebACL")


def test_prod_cannot_disable_waf() -> None:
    """Prod stacks must keep WAF enabled."""
    context = {
        **_context_for_region("us-west-2"),
        "environment": "prod",
        "allowed_origins": '["https://app.example.com"]',
        "enable_waf": "false",
    }

    with pytest.raises(ValueError, match="enable_waf cannot be false"):
        _template(context=context)


def test_prod_cannot_disable_reserved_concurrency() -> None:
    """Prod stacks must not disable reserved concurrency."""
    context = {
        **_context_for_region("us-west-2"),
        "environment": "prod",
        "allowed_origins": '["https://app.example.com"]',
        "enable_reserved_concurrency": "false",
    }

    with pytest.raises(
        ValueError,
        match="enable_reserved_concurrency cannot be false",
    ):
        _template(context=context)


def test_runtime_stack_uses_higher_reserved_concurrency_default_in_prod() -> (
    None
):
    """Prod stacks should retain the bounded higher concurrency default."""
    context = {
        **_context_for_region("us-west-2"),
        "environment": "prod",
        "allowed_origins": '["https://app.example.com"]',
    }
    bundle = _build_bundle(context=context)
    functions = _resources_of_type(bundle.resources, "AWS::Lambda::Function")
    api_resource = next(
        resource
        for resource in functions.values()
        if (
            resource["Properties"]
            .get("Environment", {})
            .get("Variables", {})
            .get("EXPORT_WORKFLOW_STATE_MACHINE_ARN")
        )
    )
    assert api_resource["Properties"]["ReservedConcurrentExecutions"] == 25


def test_runtime_stack_sets_workflow_reserved_concurrency_defaults() -> None:
    """Workflow task Lambdas should use bounded reserved concurrency."""
    bundle = _build_bundle()
    workflow_functions = _workflow_function_resources(bundle.resources)
    assert workflow_functions
    assert {
        resource["Properties"]["ReservedConcurrentExecutions"]
        for resource in workflow_functions.values()
    } == {2}
    assert {
        resource["Properties"]["Runtime"]
        for resource in workflow_functions.values()
    } == {"python3.13"}
    assert {
        resource["Properties"]["Code"]["S3Key"]
        for resource in workflow_functions.values()
    } == {_context_for_region("us-west-2")["workflow_lambda_artifact_key"]}


def test_runtime_stack_adds_s3_abort_incomplete_multipart_lifecycle() -> None:
    """The transfer bucket should enforce lifecycle cleanup controls."""
    bundle = _build_bundle()
    buckets = _resources_of_type(bundle.resources, "AWS::S3::Bucket")
    assert buckets
    bucket_props = next(iter(buckets.values()))["Properties"]
    rules = bucket_props["LifecycleConfiguration"]["Rules"]
    rules_by_id = {rule["Id"]: rule for rule in rules}
    assert (
        rules_by_id["abort-incomplete-multipart-uploads"][
            "AbortIncompleteMultipartUpload"
        ]["DaysAfterInitiation"]
        == 7
    )
    assert rules_by_id["expire-transient-workflow-artifacts"] == {
        "ExpirationInDays": 3,
        "Id": "expire-transient-workflow-artifacts",
        "Prefix": "tmp/",
        "Status": "Enabled",
    }
