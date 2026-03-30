"""Release workflow contract tests for the canonical package-release surface."""

from __future__ import annotations

from .helpers import REPO_ROOT
from .helpers import read_repo_file as _read


def test_publish_packages_workflow_has_staged_gate_contracts() -> None:
    """Publish workflow must stage, gate, and publish from immutable inputs."""
    text = _read(".github/workflows/publish-packages.yml")

    for required in [
        "name: Publish Packages",
        "release_apply_run_id",
        "scripts.release.codeartifact_gate",
        "scripts.release.npm_publish",
        "scripts.release.download_run_artifact",
        "release-apply-artifacts",
        "codeartifact-gate-report.json",
        "codeartifact-promotion-candidates.json",
        "npm-publish-report.json",
        "CODEARTIFACT_STAGING_REPOSITORY",
        "Setup Node",
        "Setup R",
        "Configure release signing",
        "Smoke test npm packages from CodeArtifact staging",
        "twine upload --repository codeartifact",
        "npm publish --no-progress",
        "publish-package-version",
        "tarball_sha256",
        "signature_sha256",
        "signature_path",
    ]:
        assert required in text, (
            f"Missing required publish contract: {required!r}"
        )

    for forbidden in [
        "workflow_run:",
        "github.event.workflow_run",
    ]:
        assert forbidden not in text


def test_promote_prod_workflow_promotes_packages_only() -> None:
    """Promotion workflow should only validate and copy staged packages."""
    wrapper_text = _read(".github/workflows/promote-prod.yml")
    reusable_text = _read(".github/workflows/reusable-promote-prod.yml")

    for required in [
        "manifest_sha256",
        "changed_units_json",
        "changed_units_path",
        "changed_units_sha256",
        "version_plan_json",
        "version_plan_path",
        "version_plan_sha256",
        "promotion_candidates_json",
        "promotion_candidates_path",
        "promotion_candidates_sha256",
        "uses: ./.github/workflows/reusable-promote-prod.yml",
        "github.ref == 'refs/heads/main'",
    ]:
        assert required in wrapper_text, (
            f"Missing required promote wrapper contract: {required!r}"
        )

    for forbidden in ["pipeline_name", "codepipeline-approve"]:
        assert forbidden not in wrapper_text
        assert forbidden not in reusable_text

    for required in [
        "CODEARTIFACT_STAGING_REPOSITORY",
        "CODEARTIFACT_PROD_REPOSITORY",
        "scripts.release.codeartifact_gate",
        "copy-package-versions",
        "codeartifact_format",
        "tarball_sha256",
        "signature_sha256",
        "validated-promotion-candidates.json",
        "sha256 mismatch",
        "expected top-level JSON",
    ]:
        assert required in reusable_text, (
            f"Missing required promote reusable contract: {required!r}"
        )


def test_release_apply_workflow_is_manual_wrapper_to_reusable_api() -> None:
    """Release apply wrapper must stay manual and delegate to shared API."""
    release_apply_text = _read(".github/workflows/release-apply.yml")
    reusable_release_apply_text = _read(
        ".github/workflows/reusable-release-apply.yml"
    )

    for required in [
        "uses: ./.github/workflows/reusable-release-apply.yml",
        "checkout_ref:",
        "release_artifact_bucket:",
        "release_signing_secret_id",
        "RELEASE_ARTIFACT_BUCKET",
        "workflow_dispatch",
        "github.ref == 'refs/heads/main'",
    ]:
        assert required in release_apply_text

    for forbidden in [
        "scripts.release.changed_units",
        "scripts.release.apply_versions",
        "workflow_run:",
    ]:
        assert forbidden not in release_apply_text

    for required in [
        "release-apply-artifacts",
        "release-apply-metadata.json",
        "api-lambda-artifact.json",
        "build_api_lambda_asset.py",
        "RELEASE_ARTIFACT_BUCKET",
        "aws s3 cp",
        "artifact_bucket",
        "artifact_key",
        "artifact_sha256",
        "release_commit_created",
        "Push signed release commit",
    ]:
        assert required in reusable_release_apply_text

    commit_index = reusable_release_apply_text.index(
        "- name: Commit release changes"
    )
    build_index = reusable_release_apply_text.index(
        "- name: Build immutable API Lambda artifact"
    )
    publish_index = reusable_release_apply_text.index(
        "- name: Publish immutable API Lambda artifact"
    )
    push_index = reusable_release_apply_text.index(
        "- name: Push signed release commit"
    )

    assert commit_index < build_index < publish_index < push_index


def test_release_plan_workflow_is_wrapper_to_reusable_api() -> None:
    """Release-plan entry workflow must call reusable release-plan API."""
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
        "validation_canonical_paths",
        "validation_legacy_404_paths",
        "report_path",
        "artifact_name",
    ]:
        assert required in wrapper_text

    for required in [
        "workflow_call:",
        "validation_status",
        "deploy_output_json",
        "deploy_output_path",
        "scripts.release.download_run_artifact",
        "scripts/release/validate_runtime_release.py",
        "post-deploy-validation-report.json",
    ]:
        assert required in reusable_text


def test_deleted_deploy_runtime_surface_is_absent() -> None:
    """Legacy deploy/runtime workflow entrypoints should be gone."""
    for rel_path in [
        ".github/workflows/deploy-dev.yml",
        ".github/workflows/reusable-bootstrap-foundation.yml",
        ".github/workflows/reusable-deploy-dev.yml",
        "buildspecs/buildspec-release.yml",
        "buildspecs/buildspec-deploy-validate.yml",
    ]:
        assert not (REPO_ROOT / rel_path).exists(), rel_path
