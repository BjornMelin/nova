"""Release workflow contract tests for staged package publication and
controlled promotion policy."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


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
    text = _read(".github/workflows/promote-prod.yml")

    for required in [
        "manifest_sha256",
        "changed_units_json",
        "version_plan_json",
        "promotion_candidates_json",
        "CODEARTIFACT_STAGING_REPOSITORY",
        "CODEARTIFACT_PROD_REPOSITORY",
        "scripts.release.codeartifact_gate",
        "copy-package-versions",
        "approve-prod-pipeline",
    ]:
        assert required in text, f"Missing required contract: {required!r}"


def test_post_deploy_validate_workflow_contracts() -> None:
    """Validate post-deploy workflow routes and artifact contracts.

    Returns:
        None.
    """
    text = _read(".github/workflows/post-deploy-validate.yml")

    for required in [
        "validation_base_url",
        "service_base_url",
        "validation_canonical_paths",
        "validation_legacy_404_paths",
        "VALIDATION_BASE_URL",
        "VALIDATION_CANONICAL_PATHS",
        "VALIDATION_LEGACY_404_PATHS",
        "scripts/release/validate_route_contract.py",
        "/v1/health/live",
        "/v1/health/ready",
        "/metrics/summary",
        "/healthz",
        "/readyz",
        "post-deploy-validation-report.json",
        "actions/upload-artifact@v4",
    ]:
        assert required in text, f"Missing required contract: {required!r}"


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
