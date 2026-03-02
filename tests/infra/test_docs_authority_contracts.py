"""Documentation authority contract tests for Nova-path runbooks."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"

ACTIVE_DOCS_PATHS = (
    DOCS_ROOT / "runbooks",
    DOCS_ROOT / "plan" / "release",
    DOCS_ROOT / "architecture" / "adr",
    DOCS_ROOT / "architecture" / "spec",
)

BANNED_DOC_PATTERNS = (
    "container-craft/docs/",
    "infra-stack/container-craft/blob",
    "infra-stack/container-craft/tree",
)


def _markdown_files(base_path: Path) -> list[Path]:
    return sorted(path for path in base_path.rglob("*.md") if path.is_file())


def test_canonical_runbook_entrypoint_exists() -> None:
    """Canonical runbook index must exist in Nova docs."""
    assert (DOCS_ROOT / "runbooks" / "README.md").is_file()


def test_active_docs_do_not_link_to_retired_container_craft_docs() -> None:
    """Active Nova docs must not point to retired container-craft docs."""
    violations: list[str] = []

    for base_path in ACTIVE_DOCS_PATHS:
        for doc in _markdown_files(base_path):
            text = doc.read_text(encoding="utf-8")
            for pattern in BANNED_DOC_PATTERNS:
                if pattern in text:
                    rel_path = doc.relative_to(REPO_ROOT)
                    violations.append(f"{rel_path}: {pattern}")

    assert not violations, (
        "Found active Nova docs linking to retired container-craft docs:\n"
        + "\n".join(violations)
    )


def test_observability_security_cost_runbook_authority_exists() -> None:
    """Batch A4 authority runbook must exist and include required constraints."""
    path = DOCS_ROOT / "runbooks" / "observability-security-cost-baseline.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")

    for required in [
        "OIDC trust-policy constraints",
        "token.actions.githubusercontent.com:aud: sts.amazonaws.com",
        "repo:${RepositoryOwner}/${RepositoryName}:ref:refs/heads/${MainBranchName}",
        "MinTaskCount",
        "MaxTaskCount",
        "MonthlyEstimatedChargesAlarm",
    ]:
        assert required in text
