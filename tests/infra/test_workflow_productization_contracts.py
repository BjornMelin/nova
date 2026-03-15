"""Workflow productization contracts for reusable workflows and composites."""

from __future__ import annotations

import yaml

from .helpers import REPO_ROOT
from .helpers import read_repo_file as _read


def test_reusable_workflow_call_apis_exist_and_are_callable() -> None:
    """Reusable workflows must expose explicit workflow_call APIs."""
    for rel_path in [
        ".github/workflows/reusable-release-plan.yml",
        ".github/workflows/reusable-release-apply.yml",
        ".github/workflows/reusable-bootstrap-foundation.yml",
        ".github/workflows/reusable-deploy-runtime.yml",
        ".github/workflows/reusable-deploy-dev.yml",
        ".github/workflows/reusable-promote-prod.yml",
        ".github/workflows/reusable-post-deploy-validate.yml",
        ".github/workflows/reusable-auth0-tenant-deploy.yml",
    ]:
        workflow = yaml.safe_load(_read(rel_path))
        assert isinstance(workflow, dict), (
            f"Expected mapping workflow for: {rel_path}"
        )
        on_contract = workflow.get("on")
        if on_contract is None:
            on_contract = workflow.get(True)
        assert isinstance(on_contract, dict), (
            f"Expected workflow on mapping for: {rel_path}"
        )
        workflow_call = on_contract.get("workflow_call")
        assert isinstance(workflow_call, dict), (
            f"Expected workflow_call mapping for: {rel_path}"
        )


def test_composite_actions_provide_shared_release_primitives() -> None:
    """Shared composite actions must exist for bootstrap and pipeline ops."""
    required_contracts = {
        ".github/actions/setup-python-uv/action.yml": [
            "using: composite",
            "actions/setup-python@v5",
            "astral-sh/setup-uv@v4",
            "uv sync",
        ],
        ".github/actions/configure-aws-oidc/action.yml": [
            "using: composite",
            "aws-actions/configure-aws-credentials@v4",
            "role-to-assume",
            "aws-region",
        ],
        ".github/actions/configure-release-signing/action.yml": [
            "using: composite",
            "aws secretsmanager get-secret-value",
            "git config commit.gpgsign true",
        ],
        ".github/actions/codepipeline-start/action.yml": [
            "using: composite",
            "codepipeline start-pipeline-execution",
            "Invalid pipeline name",
        ],
        ".github/actions/codepipeline-approve/action.yml": [
            "using: composite",
            "codepipeline get-pipeline-state",
            "codepipeline put-approval-result",
            "Approval token not found",
        ],
        ".github/actions/resolve-size-profile/action.yml": [
            "using: composite",
            "app-type",
            "size-profile",
            "container-port",
            "task-cpu",
            "task-memory",
            "desired-count",
        ],
        ".github/actions/cfn-change-set-lifecycle/action.yml": [
            "using: composite",
            "create-change-set",
            "execute-change-set",
            "no-fail-on-empty-changeset",
            "aws cloudformation describe-events",
            "--change-set-name",
            "OperationEvents",
        ],
        ".github/actions/collect-deploy-evidence/action.yml": [
            "using: composite",
            "describe-stacks",
            "get-pipeline-state",
            "deploy-evidence",
        ],
    }

    for rel_path, required_strings in required_contracts.items():
        text = _read(rel_path)
        for required in required_strings:
            assert required in text, (
                f"Missing composite action contract in {rel_path}: {required!r}"
            )

    cfn_lifecycle_text = _read(
        ".github/actions/cfn-change-set-lifecycle/action.yml"
    )
    assert "--change-set-id" not in cfn_lifecycle_text, (
        "Composite action must use change-set-name validation flow, not "
        f"legacy change-set-id queries:\n{cfn_lifecycle_text}"
    )
    assert '--query "Events[' not in cfn_lifecycle_text, (
        "Composite action must query OperationEvents instead of legacy Events "
        f"output:\n{cfn_lifecycle_text}"
    )


def test_reusable_deploy_runtime_contract_includes_typed_inputs_outputs() -> (
    None
):
    """Reusable deploy-runtime workflow must expose v1 typed contract keys."""
    workflow_text = _read(".github/workflows/reusable-deploy-runtime.yml")
    workflow = yaml.safe_load(workflow_text)
    assert isinstance(workflow, dict)
    on_contract = workflow.get("on")
    if on_contract is None:
        on_contract = workflow.get(True)
    assert isinstance(on_contract, dict)
    workflow_call = on_contract.get("workflow_call")
    assert isinstance(workflow_call, dict)

    inputs = workflow_call.get("inputs", {})
    outputs = workflow_call.get("outputs", {})
    assert isinstance(inputs, dict)
    assert isinstance(outputs, dict)

    for required in [
        "template_file",
        "image_digest",
        "custom_container_port",
        "custom_task_cpu",
        "custom_task_memory",
        "custom_desired_count",
        "app_type",
        "environment",
        "aws_region",
        "parameter_file",
        "size_profile",
        "runtime_cost_mode",
        "enable_worker",
        "approval_environment",
        "stack_name",
    ]:
        assert required in inputs

    for required in [
        "stack_name",
        "change_set_name",
        "pipeline_execution_id",
        "validation_report_path",
        "manifest_sha256",
    ]:
        assert required in outputs

    for required in (
        "resolve-size-profile",
        "cfn-change-set-lifecycle",
        "collect-deploy-evidence",
    ):
        assert required in workflow_text

    assert "image_tag" not in inputs


def test_cfn_contract_validate_workflow_exists_for_cfn_gates() -> None:
    """CI must include CFN syntax/schema and preflight contract validation."""
    text = _read(".github/workflows/cfn-contract-validate.yml")
    for required in [
        "name: CFN Contract Validate",
        "workflow_dispatch",
        "cfn-lint",
        "infra/nova/*.yml",
        "infra/nova/deploy/*.yml",
        "infra/runtime/**/*.yml",
        "test_absorbed_infra_contracts.py",
        "test_workflow_productization_contracts.py",
        "test_workflow_contract_docs.py",
        "test_docs_authority_contracts.py",
    ]:
        assert required in text


def test_reusable_deploy_dev_checks_out_workflow_source_for_local_actions() -> (
    None
):
    """Reusable deploy-dev must checkout source before local actions."""
    text = _read(".github/workflows/reusable-deploy-dev.yml")

    for required in [
        "WORKFLOW_SOURCE_REPOSITORY",
        "WORKFLOW_SOURCE_SHA",
        "github.workflow_sha",
        "actions/checkout@v4",
        "repository: ${{ env.WORKFLOW_SOURCE_REPOSITORY }}",
        "ref: ${{ env.WORKFLOW_SOURCE_SHA }}",
        "uses: ./.github/actions/configure-aws-oidc",
        "uses: ./.github/actions/codepipeline-start",
    ]:
        assert required in text


def test_canonical_runtime_deploy_script_enforces_final_posture() -> None:
    """Canonical runtime convergence must live in one operator script."""
    text = _read("scripts/release/deploy-runtime-cloudformation-environment.sh")

    for required in [
        "infra/runtime/kms.yml",
        "infra/runtime/ecr.yml",
        "infra/runtime/ecs/cluster.yml",
        "infra/runtime/file_transfer/s3.yml",
        "infra/runtime/file_transfer/async.yml",
        "infra/runtime/file_transfer/cache.yml",
        "infra/runtime/ecs/service.yml",
        "infra/runtime/file_transfer/worker.yml",
        "infra/runtime/observability/ecs-observability-baseline.yml",
        "infra/nova/deploy/service-base-url-ssm.yml",
        "--no-execute-changeset",
        "--change-set-name",
        "AssignPublicIp=DISABLED",
        "FileTransferAsyncEnabled=true",
        "FileTransferCacheEnabled=true",
        "TaskExecutionSecretArns=",
        "Runtime file-transfer bucket must not reuse the CI artifact bucket",
    ]:
        assert required in text

    assert "AllowExecutionRoleSecretsWildcard" not in text
    assert "ENV_VARS_JSON must not include IDEMPOTENCY_MODE" in text
    assert '"EnvVars=${ENV_VARS_JSON}"' not in text
    assert '"JobsQueueUrl=${JOBS_QUEUE_URL}"' in text
    assert '"JobsTableName=${JOBS_TABLE_NAME}"' in text
    assert '"ActivityTableName=${ACTIVITY_TABLE_NAME}"' in text
    assert '"CacheRedisUrlSecretArn=${CACHE_URL_SECRET_ARN}"' in text


def test_runtime_deploy_script_enforces_visibility_and_execute_mode() -> None:
    """Runtime deploy script must fail fast on invalid queue timeout.

    The script also must remain executable for operators.
    """
    rel_path = "scripts/release/deploy-runtime-cloudformation-environment.sh"
    text = _read(rel_path)

    assert (
        'if ! [[ "$JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]]; then'
        in text
    )
    assert 'JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS" -lt 1' in text
    assert 'JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS" -gt 43200' in text
    assert "between 1 and 43200 (12 hours)" in text

    script_path = REPO_ROOT / rel_path
    assert script_path.stat().st_mode & 0o111, (
        f"Expected operator script to be executable: {script_path}"
    )
