"""Documentation authority contract tests for the reduced canonical docs set."""

from __future__ import annotations

from .helpers import REPO_ROOT
from .helpers import read_repo_file as _read

DOCS_ROOT = REPO_ROOT / "docs"
AUDIT_ROOT = REPO_ROOT / ".agents" / "AUDIT_DELIVERABLES"


def test_active_docs_index_tracks_small_canonical_surface() -> None:
    """The active-docs index must define the reduced authority set."""
    text = _read("docs/overview/ACTIVE-DOCS-INDEX.md")

    for required in [
        "## Active current/baseline docs",
        "## Active target-state docs",
        "## Not active by default",
        "README.md",
        "AGENTS.md",
        "docs/README.md",
        "docs/architecture/README.md",
        "docs/architecture/requirements.md",
        "docs/overview/IMPLEMENTATION-STATUS-MATRIX.md",
        "docs/architecture/requirements-wave-2.md",
        "docs/architecture/adr/ADR-0033",
        "docs/architecture/spec/SPEC-0027` through `SPEC-0031",
        "docs/contracts/BREAKING-CHANGES-V2.md",
        "docs/history/",
        "docs/architecture/adr/superseded/",
        "docs/architecture/spec/superseded/",
        ".agents/AUDIT_DELIVERABLES/",
    ]:
        assert required in text


def test_root_authority_routers_point_to_current_indexes() -> None:
    """Root routers must direct readers through the reduced authority map."""
    readme = _read("README.md")
    agents = _read("AGENTS.md")
    docs_router = _read("docs/README.md")
    architecture_router = _read("docs/architecture/README.md")

    for text in [readme, agents]:
        for required in [
            "docs/README.md",
            "docs/architecture/README.md",
            "docs/overview/IMPLEMENTATION-STATUS-MATRIX.md",
            ".agents/AUDIT_DELIVERABLES/README_RUN_ORDER.md",
        ]:
            assert required in text

    for required in [
        "## Current implemented baseline",
        "## Approved target-state program",
        "## Historical / superseded",
        "./overview/ACTIVE-DOCS-INDEX.md",
        ".agents/AUDIT_DELIVERABLES/",
    ]:
        assert required in docs_router

    for required in [
        "pre-wave-2 implementation baseline",
        "adr/ADR-0033-canonical-serverless-platform.md",
        "adr/ADR-0038-docs-authority-reset.md",
        "spec/SPEC-0027-public-api-v2.md",
        "spec/SPEC-0031-docs-and-tests-authority-reset.md",
        "../history/",
        ".agents/AUDIT_DELIVERABLES/EXECUTIVE_AUDIT_V2.md",
    ]:
        assert required in architecture_router


def test_active_plan_directory_is_pruned_to_current_indexes() -> None:
    """The active plan directory should contain only current entrypoints."""
    plan_files = {
        path.name for path in (DOCS_ROOT / "plan").iterdir() if path.is_file()
    }

    assert plan_files == {"GREENFIELD-WAVE-2-EXECUTION.md", "PLAN.md"}
    assert not (
        DOCS_ROOT / "plan" / "greenfield-simplification-program.md"
    ).exists()
    assert not (DOCS_ROOT / "plan" / "greenfield-authority-map.md").exists()
    assert not (DOCS_ROOT / "plan" / "greenfield-evidence").exists()


def test_wave_one_material_moves_to_history_bundle() -> None:
    """Wave-one planning/evidence must live under history."""
    history_bundle = (
        DOCS_ROOT / "history" / "2026-03-greenfield-wave-1-superseded"
    )
    assert history_bundle.is_dir()

    for rel_path in [
        "greenfield-authority-map.md",
        "greenfield-simplification-program.md",
        "r-sdk-finalization-and-downstream-r-consumer-integration.md",
        "greenfield-evidence/EXECUTIVE_AUDIT.md",
        "greenfield-evidence/IMPLEMENTATION_PROGRAM.md",
    ]:
        assert (history_bundle / rel_path).is_file(), rel_path


def test_superseded_wave_one_docs_keep_original_filenames() -> None:
    """Superseded wave-one authority docs must keep their original names."""
    for rel_path in [
        "docs/architecture/adr/superseded/ADR-0033-single-runtime-auth-authority.md",
        "docs/architecture/adr/superseded/ADR-0034-bearer-jwt-public-auth-contract.md",
        "docs/architecture/adr/superseded/ADR-0035-worker-direct-result-persistence.md",
        "docs/architecture/adr/superseded/ADR-0036-native-fastapi-openapi-contract.md",
        "docs/architecture/adr/superseded/ADR-0037-async-first-public-surface.md",
        "docs/architecture/adr/superseded/ADR-0038-sdk-architecture-by-language.md",
        "docs/architecture/adr/superseded/ADR-0039-aws-target-platform.md",
        "docs/architecture/adr/superseded/ADR-0040-repo-rebaseline-after-cuts.md",
        "docs/architecture/adr/superseded/ADR-0041-shared-pure-asgi-middleware-and-errors.md",
        "docs/architecture/spec/superseded/SPEC-0027-public-http-contract-revision-and-bearer-auth.md",
        "docs/architecture/spec/superseded/SPEC-0028-worker-job-lifecycle-and-direct-result-path.md",
        "docs/architecture/spec/superseded/SPEC-0029-sdk-architecture-and-artifact-contract.md",
    ]:
        assert (REPO_ROOT / rel_path).is_file(), rel_path


def test_audit_deliverables_entrypoints_exist_for_branch_execution() -> None:
    """Branch-execution docs kept in-repo must exist at the referenced paths."""
    for rel_path in [
        AUDIT_ROOT / "README_RUN_ORDER.md",
        AUDIT_ROOT / "EXECUTIVE_AUDIT_V2.md",
        AUDIT_ROOT / "decision-matrices.md",
        AUDIT_ROOT / "findings" / "audit-findings-ledger.md",
        AUDIT_ROOT / "findings" / "repo-size-ledger.md",
        AUDIT_ROOT
        / "prompts"
        / "10_refactor_docs_authority_reset_and_archive_prune.md",
    ]:
        assert rel_path.is_file(), rel_path


def test_contracts_readme_tracks_current_schemas() -> None:
    """Contracts router should distinguish current schemas from v2 cuts."""
    text = _read("docs/contracts/README.md")

    for required in [
        "reusable-workflow-inputs-v1.schema.json",
        "reusable-workflow-outputs-v1.schema.json",
        "workflow-post-deploy-validate.schema.json",
        "workflow-auth0-tenant-ops-v1.schema.json",
        "ssm-runtime-base-url-v1.schema.json",
        "BREAKING-CHANGES-V2.md",
        "current baseline",
    ]:
        assert required in text


def test_active_docs_do_not_reference_removed_repo_root_final_plan() -> None:
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
