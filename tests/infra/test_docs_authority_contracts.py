"""Documentation authority contract tests for Nova-path runbooks."""

from __future__ import annotations

import re
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

ACTIVE_ROUTE_AUTHORITY_PATHS = (
    REPO_ROOT / "README.md",
    DOCS_ROOT / "PRD.md",
    DOCS_ROOT / "architecture" / "requirements.md",
    *ACTIVE_DOCS_PATHS,
)

LEGACY_ACTIVE_ROUTE_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9_])/api(?:/|\*)"),
    re.compile(r"(?<![A-Za-z0-9_])/healthz(?:\b|/)"),
    re.compile(r"(?<![A-Za-z0-9_])/readyz(?:\b|/)"),
)


def _markdown_files(base_path: Path) -> list[Path]:
    return sorted(path for path in base_path.rglob("*.md") if path.is_file())


def _markdown_targets(paths: tuple[Path, ...]) -> list[Path]:
    docs: list[Path] = []
    for path in paths:
        if path.is_file():
            docs.append(path)
        elif path.is_dir():
            docs.extend(_markdown_files(path))
    return sorted(docs)


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


def test_active_docs_do_not_reference_legacy_runtime_route_literals() -> None:
    """Active route authority docs must remain canonical-only."""
    violations: set[str] = set()

    for doc in _markdown_targets(ACTIVE_ROUTE_AUTHORITY_PATHS):
        text = doc.read_text(encoding="utf-8")
        for pattern in LEGACY_ACTIVE_ROUTE_PATTERNS:
            for match in pattern.finditer(text):
                rel_path = doc.relative_to(REPO_ROOT)
                violations.add(f"{rel_path}: {match.group(0)}")

    assert not violations, (
        "Found legacy runtime route literals in active docs:\n"
        + "\n".join(sorted(violations))
    )


def test_observability_security_cost_runbook_authority_exists() -> None:
    """Batch A4 authority runbook must exist.

    Also enforces required constraints for baseline hardening contract.
    """
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


def test_release_docs_include_codeartifact_staged_promotion_authority() -> None:
    """Release docs must include staged publish and controlled promotion
    policy."""
    config_values = (
        DOCS_ROOT / "plan" / "release" / "config-values-reference-guide.md"
    ).read_text(encoding="utf-8")
    release_policy = (
        DOCS_ROOT / "plan" / "release" / "RELEASE-POLICY.md"
    ).read_text(encoding="utf-8")

    for required in [
        "CODEARTIFACT_STAGING_REPOSITORY",
        "CODEARTIFACT_PROD_REPOSITORY",
        "publish-packages.yml",
        "promote-prod.yml",
    ]:
        assert required in config_values

    for required in [
        "Publish to staged channel",
        (
            "Promotion to prod channel must consume only staged "
            "and gate-validated versions"
        ),
        "RELEASE_MANIFEST_SHA256",
    ]:
        assert required in release_policy


def test_worker_lane_runbook_authority_exists() -> None:
    """Worker lane runbook must codify DLQ and queue-driven autoscaling ops."""
    path = (
        DOCS_ROOT
        / "runbooks"
        / "worker-lane-operations-and-failure-handling.md"
    )
    assert path.is_file()
    content = path.read_text(encoding="utf-8")

    for required in [
        "JobsDeadLetterQueue",
        "JobsMaxReceiveCount",
        "ApproximateNumberOfMessagesVisible",
        "ApproximateAgeOfOldestMessage",
        "queue_unavailable",
    ]:
        assert required in content
