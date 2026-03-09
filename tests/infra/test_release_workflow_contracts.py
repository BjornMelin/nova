"""Release workflow contract tests for staged package publication and
controlled promotion policy."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    """Read a repository-relative file path."""
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Expected file to exist: {path}"
    return path.read_text(encoding="utf-8")


def test_publish_packages_workflow_has_staged_gate_contracts() -> None:
    """Validate staged publish workflow contracts in the publish workflow
    file."""
    text = _read(".github/workflows/publish-packages.yml")

    for required in [
        "name: Publish Packages",
        "Nova Release Apply",
        "scripts.release.codeartifact_gate",
        "codeartifact-gate-report.json",
        "codeartifact-promotion-candidates.json",
        "CODEARTIFACT_STAGING_REPOSITORY",
        "aws codeartifact login",
        "twine upload --repository codeartifact",
    ]:
        assert required in text, f"Missing required contract: {required!r}"


def test_promote_prod_workflow_has_controlled_package_promotion_policy() -> (
    None
):
    """Validate controlled package-promotion contracts in the promote
    workflow file."""
    wrapper_text = _read(".github/workflows/promote-prod.yml")
    reusable_text = _read(".github/workflows/reusable-promote-prod.yml")

    for required in [
        "manifest_sha256",
        "changed_units_json",
        "version_plan_json",
        "promotion_candidates_json",
        "codeartifact_domain",
        "codeartifact_staging_repository",
        "codeartifact_prod_repository",
        "uses: ./.github/workflows/reusable-promote-prod.yml",
        "github.ref == 'refs/heads/main'",
    ]:
        assert required in wrapper_text, (
            f"Missing required wrapper contract: {required!r}"
        )

    for required in [
        "CODEARTIFACT_STAGING_REPOSITORY",
        "CODEARTIFACT_PROD_REPOSITORY",
        "scripts.release.codeartifact_gate",
        "copy-package-versions",
        "approve-prod-pipeline",
        "codepipeline-approve",
    ]:
        assert required in reusable_text, (
            f"Missing required reusable contract: {required!r}"
        )


def test_release_apply_workflows_are_thin_wrappers_to_reusable_api() -> None:
    """Release apply workflows must call shared reusable implementation."""
    release_apply_text = _read(".github/workflows/release-apply.yml")
    build_publish_text = _read(".github/workflows/build-and-publish-image.yml")

    for required in [
        "uses: ./.github/workflows/reusable-release-apply.yml",
        "checkout_ref:",
        "release_signing_secret_id",
        "workflow_dispatch",
    ]:
        assert required in release_apply_text, (
            f"Missing release-apply wrapper contract: {required!r}"
        )
        assert required in build_publish_text, (
            f"Missing build-and-publish-image wrapper contract: {required!r}"
        )

    assert 'workflows: ["Nova Release Plan"]' in release_apply_text
    assert 'workflows: ["Publish Packages"]' in build_publish_text

    for forbidden in [
        "scripts.release.changed_units",
        "scripts.release.apply_versions",
        "Configure git signing from Secrets Manager",
    ]:
        assert forbidden not in release_apply_text
        assert forbidden not in build_publish_text


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
    assert "workflow_call:" in reusable_release_plan_text
    for required in [
        "scripts.release.changed_units",
        "scripts.release.version_plan",
        "release-plan-artifacts",
    ]:
        assert required in reusable_release_plan_text


def test_deploy_dev_workflow_uses_reusable_api() -> None:
    """Deploy-dev entry workflow must be a thin reusable workflow wrapper."""
    wrapper_text = _read(".github/workflows/deploy-dev.yml")
    reusable_text = _read(".github/workflows/reusable-deploy-dev.yml")

    for required in [
        "uses: ./.github/workflows/reusable-deploy-dev.yml",
        "pipeline_name",
        "release_aws_role_arn",
    ]:
        assert required in wrapper_text

    for required in [
        "codepipeline-start",
        "configure-aws-oidc",
        "pipeline_name",
    ]:
        assert required in reusable_text


def test_post_deploy_validate_workflow_contracts() -> None:
    """Validate post-deploy workflow routes and artifact contracts.

    Returns:
        None.
    """
    wrapper_text = _read(".github/workflows/post-deploy-validate.yml")
    reusable_text = _read(".github/workflows/reusable-post-deploy-validate.yml")

    for required in [
        "uses: ./.github/workflows/reusable-post-deploy-validate.yml",
        "validation_base_url",
        "service_base_url",
        "validation_canonical_paths",
        "validation_legacy_404_paths",
        "report_path",
        "artifact_name",
    ]:
        assert required in wrapper_text, (
            f"Missing required wrapper contract: {required!r}"
        )

    for forbidden in [
        "scripts/release/validate_route_contract.py",
        "actions/upload-artifact@v4",
    ]:
        assert forbidden not in wrapper_text, (
            f"Wrapper should stay thin and must not include: {forbidden!r}"
        )

    for required in [
        "workflow_call:",
        "validation_base_url",
        "service_base_url",
        "validation_canonical_paths",
        "validation_legacy_404_paths",
        "report_path",
        "artifact_name",
        "validation_status",
        "VALIDATION_BASE_URL",
        "VALIDATION_CANONICAL_PATHS",
        "VALIDATION_LEGACY_404_PATHS",
        "steps.run-validation.outcome",
        "set-outputs",
        "scripts/release/validate_route_contract.py",
        "/v1/health/live",
        "/v1/health/ready",
        "/metrics/summary",
        "/healthz",
        "/readyz",
        "post-deploy-validation-report.json",
        "actions/upload-artifact@v4",
    ]:
        assert required in reusable_text, (
            f"Missing required reusable contract: {required!r}"
        )


def test_auth0_tenant_deploy_workflow_contracts() -> None:
    """Validate Auth0 tenant deploy wrapper/reusable workflow contracts."""
    wrapper_text = _read(".github/workflows/auth0-tenant-deploy.yml")
    reusable_text = _read(".github/workflows/reusable-auth0-tenant-deploy.yml")

    for required in [
        "uses: ./.github/workflows/reusable-auth0-tenant-deploy.yml",
        "environment",
        "mode",
        "allow_delete",
        "input_file",
        "mapping_file",
        "artifact_name",
        "AUTH0_DOMAIN",
        "AUTH0_CLIENT_ID",
        "AUTH0_CLIENT_SECRET",
    ]:
        assert required in wrapper_text, (
            f"Missing required wrapper contract: {required!r}"
        )

    for forbidden in [
        "a0deploy import --input_file",
        "python -m scripts.release.validate_auth0_contract",
    ]:
        assert forbidden not in wrapper_text, (
            f"Wrapper should stay thin and must not include: {forbidden!r}"
        )

    for required in [
        "workflow_call:",
        "environment:",
        "mode:",
        "input_file:",
        "mapping_file:",
        "allow_delete:",
        "operation_status:",
        "report_path:",
        "artifact_name:",
        "scripts.release.validate_auth0_contract",
        (
            "if: inputs.mode != 'validate' && "
            "steps.validate-contract.outcome == 'success'"
        ),
        (
            "if: inputs.mode == 'import' && "
            "steps.validate-contract.outcome == 'success'"
        ),
        (
            "if: inputs.mode == 'export' && "
            "steps.validate-contract.outcome == 'success'"
        ),
        "a0deploy import --input_file",
        "a0deploy export --format yaml",
        "auth0-tenant-ops-report.json",
        "actions/upload-artifact@v4",
    ]:
        assert required in reusable_text, (
            f"Missing required reusable contract: {required!r}"
        )

    for forbidden in [
        "id: validate-contract\n        continue-on-error: true",
        (
            "id: run-import\n"
            "        if: inputs.mode == 'import'\n"
            "        continue-on-error: true"
        ),
        (
            "id: run-export\n"
            "        if: inputs.mode == 'export'\n"
            "        continue-on-error: true"
        ),
    ]:
        assert forbidden not in reusable_text, (
            "Reusable workflow should fail fast and must not include: "
            f"{forbidden!r}"
        )


def test_deploy_validate_buildspec_enforces_route_contracts() -> None:
    """Validate CodeBuild deploy validation buildspec contracts.

    Returns:
        None.
    """
    text = _read("buildspecs/buildspec-deploy-validate.yml")
    validator_script = _read("scripts/release/validate_route_contract.py")

    for required in [
        "VALIDATION_BASE_URL",
        "SERVICE_BASE_URL",
        "scripts/release/validate_route_contract.py",
        "deploy-validation-report.json",
        "VALIDATION_STATUS",
    ]:
        assert required in text, f"Missing required contract: {required!r}"

    for required in [
        "/v1/health/live",
        "/v1/health/ready",
        "/metrics/summary",
        "/healthz",
        "/readyz",
        "status == 404",
    ]:
        assert required in validator_script, (
            f"Missing required contract in validator script: {required!r}"
        )
