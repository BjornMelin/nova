"""Workflow productization contracts for reusable workflows and composites."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


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
        text = _read(rel_path)
        assert "on:" in text
        assert "workflow_call:" in text


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
    assert "--change-set-id" not in cfn_lifecycle_text
    assert '--query "Events[' not in cfn_lifecycle_text


def test_reusable_deploy_runtime_contract_includes_typed_inputs_outputs() -> (
    None
):
    """Reusable deploy-runtime workflow must expose v1 typed contract keys."""
    text = _read(".github/workflows/reusable-deploy-runtime.yml")

    for required in [
        "workflow_call:",
        "app_type:",
        "environment:",
        "aws_region:",
        "parameter_file:",
        "size_profile:",
        "enable_worker:",
        "approval_environment:",
        "stack_name:",
        "change_set_name:",
        "pipeline_execution_id:",
        "validation_report_path:",
        "manifest_sha256:",
        "resolve-size-profile",
        "cfn-change-set-lifecycle",
        "collect-deploy-evidence",
        "docs/plan/release/RELEASE-VERSION-MANIFEST.md",
    ]:
        assert required in text

    assert "sha256sum .artifacts/deploy-evidence.json" not in text


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
        "test_workflow_contract_docs.py",
        "test_docs_authority_contracts.py",
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
        "IdempotencyMode=shared_required",
        "FileTransferAsyncEnabled=true",
        "FileTransferCacheEnabled=true",
        "TaskExecutionSecretArns=",
        "Runtime file-transfer bucket must not reuse the CI artifact bucket",
    ]:
        assert required in text

    assert "AllowExecutionRoleSecretsWildcard" not in text
