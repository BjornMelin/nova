"""Release workflow contract tests for staged package publication and
controlled promotion policy."""

from __future__ import annotations

import yaml

from .helpers import REPO_ROOT
from .helpers import read_repo_file as _read


def test_publish_packages_workflow_has_staged_gate_contracts() -> None:
    """Validate staged publish workflow contracts in the publish workflow
    file."""
    text = _read(".github/workflows/publish-packages.yml")

    for required in [
        "name: Publish Packages",
        "Nova Release Apply",
        "scripts.release.codeartifact_gate",
        "scripts.release.npm_publish",
        "scripts.release.download_run_artifact",
        "codeartifact-gate-report.json",
        "codeartifact-promotion-candidates.json",
        "npm-publish-report.json",
        "release-apply-artifacts",
        "release_apply_run_id",
        "CODEARTIFACT_STAGING_REPOSITORY",
        "Setup Node",
        "Setup R",
        "Configure release signing",
        "steps.release-units.outputs.has_r_units == 'true'",
        "steps.release-units.outputs.has_r_units",
        "--r-publish-report",
        "published_assets",
        "tarball_sha256",
        "signature_sha256",
        "signature_path",
        "asset_name",
        "asset_path",
        "asset_sha256",
        "asset_exists",
        "skipped",
        "No R packages changed; skipping R build/sign.",
        "aws codeartifact get-repository-endpoint",
        "aws codeartifact login",
        "twine upload --repository codeartifact",
        "npm publish --no-progress",
        "Build, check, and sign R packages",
        "publish-package-version",
        "codeartifact_format",
        "generic",
        "Smoke test npm packages from CodeArtifact staging",
    ]:
        assert required in text, f"Missing required contract: {required!r}"

    assert "fileb://" not in text, (
        "R publish assets should use plain file paths for CodeArtifact upload"
    )

    for forbidden in [
        "python -m scripts.release.changed_units",
        "python -m scripts.release.version_plan",
        "Compute release artifacts",
    ]:
        assert forbidden not in text, (
            "Publish workflow must consume immutable artifacts, not "
            f"recompute: {forbidden!r}"
        )


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
        "changed_units_path",
        "changed_units_sha256",
        "version_plan_json",
        "version_plan_path",
        "version_plan_sha256",
        "promotion_candidates_json",
        "promotion_candidates_path",
        "promotion_candidates_sha256",
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
        "EXPECTED_CHANGED_UNITS_SHA256",
        "EXPECTED_VERSION_PLAN_SHA256",
        "EXPECTED_PROMOTION_CANDIDATES_SHA256",
        "copy-package-versions",
        "codeartifact_format",
        "tarball_sha256",
        "signature_sha256",
        "missing a valid tarball sha256",
        "missing a valid signature sha256",
        "--namespace",
        "generic",
        "approve-prod-pipeline",
        "codepipeline-approve",
    ]:
        assert required in reusable_text, (
            f"Missing required reusable contract: {required!r}"
        )

    for required in [
        "require_sha256",
        "validate_json_source",
        "absolute path is not allowed",
        "sha256 mismatch",
        "expected top-level JSON",
        ".artifacts/validated-promotion-candidates.json",
    ]:
        assert required in reusable_text, (
            "Reusable promote workflow must enforce strict, immutable "
            f"promotion input validation: {required!r}"
        )


def test_release_apply_workflow_is_manual_wrapper_to_reusable_api() -> None:
    """Release apply wrapper must stay manual and delegate to shared API."""
    release_apply_text = _read(".github/workflows/release-apply.yml")

    for required in [
        "uses: ./.github/workflows/reusable-release-apply.yml",
        "checkout_ref:",
        "release_signing_secret_id",
        "workflow_dispatch",
        "github.ref == 'refs/heads/main'",
    ]:
        assert required in release_apply_text, (
            f"Missing release-apply wrapper contract: {required!r}"
        )

    assert 'workflows: ["Nova Release Plan"]' not in release_apply_text
    assert "workflow_run:" not in release_apply_text
    assert "github.event.workflow_run.head_sha" not in release_apply_text

    for forbidden in [
        "scripts.release.changed_units",
        "scripts.release.apply_versions",
        "Configure git signing from Secrets Manager",
    ]:
        assert forbidden not in release_apply_text

    assert not (
        REPO_ROOT / ".github" / "workflows" / "build-and-publish-image.yml"
    ).exists()


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
    assert "push:" not in release_plan_text
    assert "github.ref == 'refs/heads/main'" in release_plan_text
    assert "workflow_call:" in reusable_release_plan_text
    for required in [
        "scripts.release.changed_units",
        "scripts.release.version_plan",
        "release-plan-artifacts",
    ]:
        assert required in reusable_release_plan_text


def test_publish_packages_workflow_requires_explicit_release_apply_run_id() -> (
    None
):
    """Publish workflow must stay manual and use immutable apply inputs."""
    text = _read(".github/workflows/publish-packages.yml")

    for required in [
        "workflow_dispatch",
        "release_apply_run_id",
        "required: true",
        "github.ref == 'refs/heads/main'",
        'version: "0.10.10"',
    ]:
        assert required in text

    for forbidden in [
        "workflow_run:",
        "github.event.workflow_run",
    ]:
        assert forbidden not in text


def test_publish_packages_workflow_runs_codeartifact_gate_before_publish() -> (
    None
):
    """Publish workflow must fail closed before any staging side effects."""
    text = _read(".github/workflows/publish-packages.yml")

    gate_index = text.index("- name: Run CodeArtifact release gates")
    python_publish_index = text.index(
        "- name: Publish to CodeArtifact staging repository"
    )
    npm_publish_index = text.index(
        "- name: Publish npm packages to CodeArtifact staging repository"
    )
    r_publish_index = text.index(
        "- name: Publish R packages to CodeArtifact staging repository"
    )
    smoke_index = text.index(
        "- name: Smoke test npm packages from CodeArtifact staging"
    )

    assert gate_index < python_publish_index
    assert gate_index < npm_publish_index
    assert gate_index < r_publish_index
    assert gate_index < smoke_index


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

    wrapper_workflow = yaml.safe_load(wrapper_text)
    assert isinstance(wrapper_workflow, dict)
    wrapper_jobs = wrapper_workflow.get("jobs")
    assert isinstance(wrapper_jobs, dict), "Expected jobs mapping in wrapper"

    auth0_reusable_workflow_path = (
        "./.github/workflows/reusable-auth0-tenant-deploy.yml"
    )

    auth0_jobs = [
        value
        for value in wrapper_jobs.values()
        if isinstance(value, dict)
        and value.get("uses") == auth0_reusable_workflow_path
    ]
    assert len(auth0_jobs) == 1, (
        "Expected exactly one wrapper job using reusable-auth0-tenant-deploy"
    )
    auth0_job = auth0_jobs[0]

    for required in [
        "uses: ./.github/workflows/reusable-auth0-tenant-deploy.yml",
        "environment",
        "mode",
        "allow_delete",
        "input_file",
        "mapping_file",
        "artifact_name",
    ]:
        assert required in wrapper_text, (
            f"Missing required wrapper contract: {required!r}"
        )

    auth0_secrets = auth0_job.get("secrets", {})
    if auth0_secrets != "inherit":
        assert isinstance(auth0_secrets, dict), (
            "Wrapper secrets must be either inherit or a mapping"
        )

        for required_secret in [
            "AUTH0_DOMAIN",
            "AUTH0_CLIENT_ID",
            "AUTH0_CLIENT_SECRET",
        ]:
            assert any(
                required_secret in str(secret_reference)
                for secret_reference in auth0_secrets.values()
            ), f"Missing required wrapper secret reference: {required_secret}"

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
