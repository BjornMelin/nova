"""Release workflow contract tests for the reduced AWS-native surface."""

from __future__ import annotations

from .helpers import REPO_ROOT, read_repo_file as _read


def test_release_plan_workflow_is_wrapper_to_reusable_api() -> None:
    """Release-plan entry workflow must call the reusable release-plan API."""
    release_plan_text = _read(".github/workflows/release-plan.yml")
    reusable_release_plan_text = _read(
        ".github/workflows/reusable-release-plan.yml"
    )

    assert (
        "uses: ./.github/workflows/reusable-release-plan.yml"
        in release_plan_text
    )
    assert "workflow_dispatch" in release_plan_text
    assert "github.ref == 'refs/heads/main'" in release_plan_text

    for required in [
        "scripts.release.changed_units",
        "scripts.release.version_plan",
        "release-plan-artifacts",
    ]:
        assert required in reusable_release_plan_text


def test_post_deploy_validate_workflow_contracts() -> None:
    """Post-deploy validation must resolve deploy-output authority first."""
    wrapper_text = _read(".github/workflows/post-deploy-validate.yml")
    reusable_text = _read(".github/workflows/reusable-post-deploy-validate.yml")

    for required in [
        "uses: ./.github/workflows/reusable-post-deploy-validate.yml",
        "deploy_run_id",
        "deploy_repo",
        "deploy_artifact_name",
        "aws_role_to_assume",
        "report_path",
        "artifact_name",
    ]:
        assert required in wrapper_text

    for required in [
        "workflow_call:",
        "validation_status",
        "aws_runtime_checks_status",
        "deploy_output_json",
        "deploy_output_path",
        "aws-actions/configure-aws-credentials@8df5847569e6427dd6c4fb1cf565c83acfa8afa7",
        "--aws-runtime-checks",
        "scripts.release.download_run_artifact",
        "scripts/release/validate_runtime_release.py",
        "post-deploy-validation-report.json",
        "Post-deploy runtime validation failed.",
    ]:
        assert required in reusable_text


def test_aws_native_release_buildspecs_emit_deploy_output_authority() -> None:
    """Release deploy buildspecs must rebuild deploy-output artifacts."""
    for rel_path in [
        "infra/nova_cdk/buildspecs/release-publish-and-deploy-dev.yml",
        "infra/nova_cdk/buildspecs/release-promote-and-deploy-prod.yml",
    ]:
        text = _read(rel_path)
        for required in [
            "scripts.release.resolve_deploy_output build",
            "aws cloudformation describe-stacks",
            "deploy-output.json",
            "deploy-output.sha256",
            "CODEPIPELINE_EXECUTION_ID",
            "RELEASE_PIPELINE_NAME",
        ]:
            assert required in text, rel_path


def test_release_buildspecs_pin_uv_version() -> None:
    """Release buildspecs must pin uv to the repo-required version."""
    pinned_buildspecs = [
        "infra/nova_cdk/buildspecs/release-validate.yml",
        "infra/nova_cdk/buildspecs/release-publish-and-deploy-dev.yml",
        "infra/nova_cdk/buildspecs/release-promote-and-deploy-prod.yml",
    ]
    for rel_path in pinned_buildspecs:
        text = _read(rel_path)
        for required in [
            "export UV_VERSION=0.11.2",
            'export UV_TARBALL="uv-x86_64-unknown-linux-gnu.tar.gz"',
            "sha256sum -c",
            'install "/tmp/uv-x86_64-unknown-linux-gnu/uv" /usr/local/bin/uv',
        ]:
            assert required in text, rel_path
        assert "astral.sh/uv/install.sh" not in text, rel_path


def test_release_buildspec_heredocs_use_literal_yaml_blocks() -> None:
    """Python heredocs must use literal YAML blocks."""
    for rel_path in [
        "infra/nova_cdk/buildspecs/release-publish-and-deploy-dev.yml",
        "infra/nova_cdk/buildspecs/release-promote-and-deploy-prod.yml",
    ]:
        lines = _read(rel_path).splitlines()
        for index, line in enumerate(lines):
            if "<<'PY'" not in line:
                continue
            assert index > 0, rel_path
            assert lines[index - 1].strip() == "- |", (
                rel_path,
                index + 1,
                lines[index - 1],
            )


def test_release_buildspecs_use_module_invocation_for_release_scripts() -> None:
    """Release helpers must be invoked with ``python -m`` in CodeBuild."""
    for rel_path in [
        "infra/nova_cdk/buildspecs/release-publish-and-deploy-dev.yml",
        "infra/nova_cdk/buildspecs/release-promote-and-deploy-prod.yml",
    ]:
        text = _read(rel_path)
        assert "uv run python scripts/release/" not in text, rel_path
        assert "python scripts/release/" not in text, rel_path


def test_deleted_gitHub_release_executor_surface_is_absent() -> None:
    """GitHub release executor workflows should be retired."""
    for rel_path in [
        ".github/workflows/release-apply.yml",
        ".github/workflows/reusable-release-apply.yml",
        ".github/workflows/publish-packages.yml",
        ".github/workflows/deploy-runtime.yml",
        ".github/workflows/reusable-deploy-runtime.yml",
        ".github/workflows/promote-prod.yml",
        ".github/workflows/reusable-promote-prod.yml",
    ]:
        assert not (REPO_ROOT / rel_path).exists(), rel_path


def test_deleted_deploy_runtime_surface_is_absent() -> None:
    """Legacy deploy/runtime workflow entrypoints should stay gone."""
    for rel_path in [
        ".github/workflows/deploy-dev.yml",
        ".github/workflows/reusable-bootstrap-foundation.yml",
        ".github/workflows/reusable-deploy-dev.yml",
        "buildspecs/buildspec-release.yml",
        "buildspecs/buildspec-deploy-validate.yml",
    ]:
        assert not (REPO_ROOT / rel_path).exists(), rel_path
