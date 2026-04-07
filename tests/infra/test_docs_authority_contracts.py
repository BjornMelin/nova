"""Documentation authority contract tests for the canonical docs set."""

from __future__ import annotations

from pathlib import Path

from .helpers import REPO_ROOT, read_repo_file as _read

DOCS_ROOT = REPO_ROOT / "docs"


def _repo_paths(*paths: str) -> list[Path]:
    """Build absolute repo paths from repo-relative strings."""
    return [REPO_ROOT / path for path in paths]


def test_active_docs_index_tracks_canonical_surface() -> None:
    """The active-docs index must define the reduced canonical surface."""
    text = _read("docs/overview/ACTIVE-DOCS-INDEX.md")

    for required in [
        "## Active canonical docs",
        "README.md",
        "AGENTS.md",
        "docs/README.md",
        "docs/architecture/README.md",
        "docs/overview/IMPLEMENTATION-STATUS-MATRIX.md",
        "docs/contracts/README.md",
        "docs/runbooks/README.md",
        "docs/clients/README.md",
        "release/README.md",
        "docs/plan/GREENFIELD-WAVE-2-EXECUTION.md",
        "docs/architecture/adr/ADR-0033` through `ADR-0039",
        "docs/architecture/spec/SPEC-0027` through `SPEC-0031",
        "docs/contracts/deploy-output-authority-v2.schema.json",
        "docs/contracts/workflow-post-deploy-validate.schema.json",
        "docs/runbooks/release/release-runbook.md",
        "infra/nova_cdk/README.md",
        "docs/architecture/adr/index.md",
        "docs/architecture/spec/index.md",
        "docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md",
        "docs/architecture/adr/ADR-0011-cicd-hybrid-github-aws-promotion.md",
        "docs/architecture/spec/SPEC-0004-ci-cd-and-docs.md",
        "docs/history/",
        "docs/plan/PLAN.md",
        "## Active supporting docs",
    ]:
        assert required in text

    for forbidden in [
        "docs/overview/CANONICAL-TARGET-2026-04.md",
        "docs/architecture/spec/superseded/SPEC-0000-http-api-contract.md",
        "docs/overview/DEPENDENCY-LEVERAGE-AUDIT.md",
        "docs/overview/ENTROPY-REDUCTION-LEDGER.md",
        "docs/standards/DECISION-FRAMEWORKS-GREENFIELD-2026.md",
        "docs/architecture/requirements-wave-2.md",
    ]:
        assert forbidden not in text


def test_root_authority_routers_point_to_canonical_indexes() -> None:
    """Root routers must direct readers through the canonical authority map."""
    readme = _read("README.md")
    agents = _read("AGENTS.md")
    docs_router = _read("docs/README.md")
    architecture_router = _read("docs/architecture/README.md")

    for text in [readme, agents]:
        for required in [
            "docs/README.md",
            "docs/architecture/README.md",
            "docs/overview/IMPLEMENTATION-STATUS-MATRIX.md",
        ]:
            assert required in text

    for required in [
        "## Active canonical docs",
        "## Active architecture/program authority",
        "## Active supporting architecture/program docs",
        "## Historical / superseded",
        "./overview/ACTIVE-DOCS-INDEX.md",
        "./contracts/deploy-output-authority-v2.schema.json",
        "./runbooks/release/release-runbook.md",
    ]:
        assert required in docs_router

    for required in [
        "canonical wave-2 serverless baseline",
        "adr/ADR-0033-canonical-serverless-platform.md",
        "spec/SPEC-0031-docs-and-tests-authority-reset.md",
        "../history/",
        "deploy-output authority",
        "../contracts/deploy-output-authority-v2.schema.json",
    ]:
        assert required in architecture_router

    for forbidden in [
        "./overview/CANONICAL-TARGET-2026-04.md",
        "SPEC-0000-http-api-contract.md",
    ]:
        assert forbidden not in docs_router


def test_spec_index_keeps_spec_0020_out_of_active_authority() -> None:
    """SPEC-0020 must live under superseded rather than the root index path."""
    text = _read("docs/architecture/spec/index.md")
    assert "## Active supporting specs" in text
    assert "## Historical / superseded specs" in text
    assert (
        "./SPEC-0020-architecture-authority-pack-and-documentation-"
        "synchronization-contract.md"
    ) not in text
    assert (
        "./superseded/SPEC-0020-architecture-authority-pack-and-"
        "documentation-synchronization-contract.md"
    ) in text


def test_moved_superseded_docs_live_only_in_archive_dirs() -> None:
    """Moved superseded docs must no longer remain at root ADR/SPEC paths."""
    moved_root_paths = _repo_paths(
        "docs/architecture/adr/ADR-0001-deployment-on-ecs-fargate-behind-alb.md",
        "docs/architecture/adr/ADR-0006-async-orchestration-sqs-ecs-worker.md",
        "docs/architecture/adr/ADR-0007-two-tier-cache-and-idempotency-store.md",
        "docs/architecture/adr/ADR-0012-no-lambda-runtime-scope.md",
        "docs/architecture/adr/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md",
        "docs/architecture/spec/SPEC-0008-async-jobs-and-worker-orchestration.md",
        "docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md",
        "docs/architecture/spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md",
        "docs/architecture/spec/SPEC-0024-cloudformation-module-contract.md",
    )
    moved_superseded_paths = _repo_paths(
        "docs/architecture/adr/superseded/ADR-0001-deployment-on-ecs-fargate-behind-alb.md",
        "docs/architecture/adr/superseded/ADR-0006-async-orchestration-sqs-ecs-worker.md",
        "docs/architecture/adr/superseded/ADR-0007-two-tier-cache-and-idempotency-store.md",
        "docs/architecture/adr/superseded/ADR-0012-no-lambda-runtime-scope.md",
        "docs/architecture/adr/superseded/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md",
        "docs/architecture/spec/superseded/SPEC-0008-async-jobs-and-worker-orchestration.md",
        "docs/architecture/spec/superseded/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md",
        "docs/architecture/spec/superseded/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md",
        "docs/architecture/spec/superseded/SPEC-0024-cloudformation-module-contract.md",
    )

    for path in moved_root_paths:
        assert not path.exists(), path

    for path in moved_superseded_paths:
        assert path.exists(), path


def test_active_plan_directory_is_pruned_to_current_indexes() -> None:
    """The plan directory should contain the current historical entrypoints."""
    plan_files = {
        path.name for path in (DOCS_ROOT / "plan").iterdir() if path.is_file()
    }

    assert plan_files == {"GREENFIELD-WAVE-2-EXECUTION.md", "PLAN.md"}


def test_contracts_readme_tracks_current_schemas() -> None:
    """Contracts router should track the surviving machine-readable schemas."""
    text = _read("docs/contracts/README.md")

    for required in [
        "release-artifacts-v1.schema.json",
        "deploy-output-authority-v2.schema.json",
        "release-prep-v1.schema.json",
        "release-execution-manifest-v1.schema.json",
        "workflow-post-deploy-validate.schema.json",
        "workflow-auth0-tenant-deploy.schema.json",
        "workflow-auth0-tenant-ops-v1.schema.json",
        "browser-live-validation-report.schema.json",
        "BREAKING-CHANGES-V2.md",
    ]:
        assert required in text

    for forbidden in [
        "reusable-workflow-inputs-v1.schema.json",
        "reusable-workflow-outputs-v1.schema.json",
        "deploy-size-profiles-v1.json",
        "ssm-runtime-base-url-v1.schema.json",
    ]:
        assert forbidden not in text


def test_active_docs_do_not_reference_removed_root_final_plan() -> None:
    """Active docs must not point back to the removed root FINAL-PLAN.md."""
    violations: list[str] = []

    for path in [
        REPO_ROOT / "README.md",
        REPO_ROOT / "AGENTS.md",
        *DOCS_ROOT.rglob("*.md"),
    ]:
        relative = path.relative_to(REPO_ROOT)
        if "history" in relative.parts or "superseded" in relative.parts:
            continue
        if "FINAL-PLAN.md" in path.read_text(encoding="utf-8"):
            violations.append(str(relative))

    assert not violations, "\n".join(violations)


def test_active_routers_do_not_promote_superseded_http_api_authority() -> None:
    """Active routers should not point readers at superseded HTTP API docs."""
    for rel_path in [
        "docs/README.md",
        "docs/architecture/README.md",
        "docs/runbooks/release/release-policy.md",
        "docs/runbooks/release/release-runbook.md",
        "docs/runbooks/provisioning/github-actions-secrets-and-vars.md",
    ]:
        assert "SPEC-0000-http-api-contract.md" not in _read(rel_path), rel_path


def test_consumer_docs_treat_deploy_output_as_runtime_authority() -> None:
    """Consumer docs should prefer deploy-output over free-text URLs."""
    clients_readme = _read("docs/clients/README.md")
    integration_guide = _read(
        "docs/clients/post-deploy-validation-integration-guide.md"
    )

    assert "deploy-output.json" in clients_readme
    assert "NOVA_API_BASE_URL" in clients_readme
    assert "deploy-output.json" in integration_guide
    assert (
        "Validation resolves its target from the authoritative deploy-output "
        "artifact" in integration_guide
    )
    assert "manually configured" in integration_guide
    assert "`NOVA_API_BASE_URL`" in integration_guide


def test_release_docs_describe_runtime_truth_validation() -> None:
    """Release docs should describe provenance-aware runtime validation."""
    release_readme = _read("docs/runbooks/release/README.md")
    release_runbook = _read("docs/runbooks/release/release-runbook.md")

    assert "runtime validation" in release_readme
    assert "protected auth" in release_runbook
    assert "browser CORS preflight" in release_runbook


def test_cdk_docs_and_entrypoint_capture_bucket_warning_acknowledgement() -> (
    None
):
    """The CDK app should acknowledge the scoped S3 bucket code warning."""
    app_text = _read("infra/nova_cdk/app.py")
    cdk_readme = _read("infra/nova_cdk/README.md")

    assert "Annotations.of(app).acknowledge_warning(" in app_text
    assert (
        "@aws-cdk/aws-lambda:codeFromBucketObjectVersionNotSpecified"
        in app_text
    )
    assert "immutable content-addressed API Lambda artifact keys" in app_text

    for required in [
        "Code.fromBucket()` without `objectVersion`",
        "immutable artifact key plus",
        "api_lambda_artifact_sha256",
        "warning is acknowledged at the app level",
    ]:
        assert required in cdk_readme
