"""Release workflow contract tests for staged package publication.

And controlled promotion policy.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_publish_packages_workflow_has_staged_gate_contracts() -> None:
    """Assert publish workflow contains required gate contract markers."""
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
    """Assert prod promotion workflow exposes controlled
    gate/promotion markers."""
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
