"""Documentation authority contract tests for the canonical docs set."""

from __future__ import annotations

from .helpers import REPO_ROOT
from .helpers import read_repo_file as _read

DOCS_ROOT = REPO_ROOT / "docs"


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
        "docs/release/README.md",
        "docs/architecture/adr/ADR-0033` through `ADR-0038",
        "docs/architecture/spec/SPEC-0027` through `SPEC-0031",
        "docs/history/",
        "docs/plan/PLAN.md",
    ]:
        assert required in text


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
        "## Historical / superseded",
        "./overview/ACTIVE-DOCS-INDEX.md",
    ]:
        assert required in docs_router

    for required in [
        "canonical wave-2 serverless baseline",
        "adr/ADR-0033-canonical-serverless-platform.md",
        "spec/SPEC-0031-docs-and-tests-authority-reset.md",
        "../history/",
    ]:
        assert required in architecture_router


def test_active_plan_directory_is_pruned_to_current_indexes() -> None:
    """The plan directory should contain only historical entrypoints."""
    plan_files = {
        path.name for path in (DOCS_ROOT / "plan").iterdir() if path.is_file()
    }

    assert plan_files == {"GREENFIELD-WAVE-2-EXECUTION.md", "PLAN.md"}


def test_contracts_readme_tracks_current_schemas() -> None:
    """Contracts router should track the surviving machine-readable schemas."""
    text = _read("docs/contracts/README.md")

    for required in [
        "release-artifacts-v1.schema.json",
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
