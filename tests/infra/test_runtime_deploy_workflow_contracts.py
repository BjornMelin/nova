"""Workflow contract tests for the repo-owned runtime deployment surface."""

from __future__ import annotations

from .helpers import read_repo_file as _read


def test_deploy_runtime_wrapper_calls_reusable_api_and_validation() -> None:
    """Deploy wrapper must remain a thin entrypoint on top of reusable APIs."""
    text = _read(".github/workflows/deploy-runtime.yml")

    for required in [
        "uses: ./.github/workflows/reusable-deploy-runtime.yml",
        "uses: ./.github/workflows/reusable-post-deploy-validate.yml",
        "release_apply_run_id",
        "release_apply_artifact_name",
        "deploy_output_artifact_name",
        "RUNTIME_DEPLOY_AWS_ROLE_ARN",
        "RUNTIME_CFN_EXECUTION_ROLE_ARN",
        "RUNTIME_API_DOMAIN_NAME",
        "RUNTIME_CERTIFICATE_ARN",
        "RUNTIME_HOSTED_ZONE_ID",
        "RUNTIME_HOSTED_ZONE_NAME",
        "RUNTIME_JWT_ISSUER",
        "RUNTIME_JWT_AUDIENCE",
        "RUNTIME_JWT_JWKS_URL",
        "github.run_id",
        "github.ref == 'refs/heads/main'",
    ]:
        assert required in text

    for forbidden in [
        "CodePipeline",
        "CodeBuild",
        "validation_base_url",
    ]:
        assert forbidden not in text


def test_reusable_deploy_runtime_uses_immutable_release_inputs() -> None:
    """Reusable deploy workflow must emit authority from immutable inputs."""
    text = _read(".github/workflows/reusable-deploy-runtime.yml")

    for required in [
        "workflow_call:",
        "release_apply_run_id",
        "release_apply_artifact_name",
        "release_apply_repo",
        "runtime_cfn_execution_role_arn",
        "actions: read",
        "hosted_zone_id",
        "hosted_zone_name",
        "Setup Node",
        "docker/setup-qemu-action",
        "docker/setup-buildx-action",
        "runtime_deploy_aws_role_arn",
        "scripts.release.download_run_artifact",
        "emit_api_lambda_artifact_env.py",
        "aws sts get-caller-identity",
        "aws cloudformation describe-stacks",
        "npx aws-cdk@2.1107.0 deploy",
        "resolve_deploy_output.py build",
        "resolve_deploy_output.py emit",
        "deploy-output.sha256",
        "actions/attest@v4",
        "actions/upload-artifact",
        "deploy_output_sha256",
        "public_base_url",
        "runtime_version",
        "release_commit_sha",
        (
            "release_apply_repo must be empty or match the workflow source "
            "repository"
        ),
    ]:
        assert required in text

    for forbidden in [
        "CodePipeline",
        "CodeBuild",
        "validation_base_url",
        "reusable-deploy-dev",
    ]:
        assert forbidden not in text

    assert '--role-arn "${{ inputs.runtime_cfn_execution_role_arn }}"' in text

    download_index = text.index("Download immutable release-apply artifacts")
    checkout_index = text.index("Checkout immutable release commit")
    deploy_index = text.index("Deploy runtime stack with CDK")
    output_index = text.index("Build deploy-output authority artifact")
    upload_index = text.index("Upload deploy-output authority artifact")

    assert (
        download_index
        < checkout_index
        < deploy_index
        < output_index
        < upload_index
    )
