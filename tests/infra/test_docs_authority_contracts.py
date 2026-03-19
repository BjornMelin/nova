"""Documentation authority contract tests for Nova-path runbooks."""

from __future__ import annotations

import re
from pathlib import Path

from .helpers import REPO_ROOT
from .helpers import read_repo_file as _read

DOCS_ROOT = REPO_ROOT / "docs"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"

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
STANDARDS_ROOT = DOCS_ROOT / "standards"

LEGACY_ACTIVE_ROUTE_PATTERNS = (
    re.compile(r"/api(?:/|\*)"),
    re.compile(r"/healthz(?:\b|/)"),
    re.compile(r"/readyz(?:\b|/)"),
)
VALIDATION_DOC_PATH = (
    DOCS_ROOT / "plan" / "release" / "config-values-reference-guide.md"
)
RUNTIME_CONFIG_CONTRACT_DOC_PATH = (
    DOCS_ROOT / "plan" / "release" / "runtime-config-contract.generated.md"
)


def _markdown_files(base_path: Path) -> list[Path]:
    return sorted(
        path
        for path in base_path.rglob("*.md")
        if path.is_file()
        and "superseded" not in path.parts
        and "history" not in path.parts
    )


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


def test_standards_entrypoint_exists() -> None:
    """Canonical standards index must exist for deeper operator guidance."""
    assert (STANDARDS_ROOT / "README.md").is_file()
    assert (STANDARDS_ROOT / "repository-engineering-standards.md").is_file()


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
        if doc == VALIDATION_DOC_PATH:
            continue

        text = doc.read_text(encoding="utf-8")
        if "validation_legacy_404_paths" in text:
            continue

        for pattern in LEGACY_ACTIVE_ROUTE_PATTERNS:
            for match in pattern.finditer(text):
                context = text[max(0, match.start() - 24) : match.start()]
                if "http" in context or "https" in context:
                    continue
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
        "runtime-config-contract.generated.md",
    ]:
        assert required in config_values

    for required in [
        "Publish to staged channel",
        (
            "Promotion to prod channel must consume only staged "
            "and gate-validated versions"
        ),
        "RELEASE_MANIFEST_SHA256",
        "Release control-plane cost posture",
        "nova-codebuild-release",
        "nova-ci-cd",
        "day-0-operator-command-pack.sh",
        "R conformance helper fails the lane",
    ]:
        assert required in release_policy

    runbook_text = (
        DOCS_ROOT / "plan" / "release" / "RELEASE-RUNBOOK.md"
    ).read_text(encoding="utf-8")
    for required in [
        "shared conformance helper",
        "scripts/checks/verify_r_cmd_check.sh",
        "fails the R lane if `R CMD check`",
        "reports warnings",
    ]:
        assert required in runbook_text


def test_generated_runtime_config_contract_doc_exists() -> None:
    """Generated runtime config doc must stay present and self-describing."""
    assert RUNTIME_CONFIG_CONTRACT_DOC_PATH.is_file()
    text = RUNTIME_CONFIG_CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    for required in [
        "scripts/release/generate_runtime_config_contract.py",
        "packages/nova_file_api/src/nova_file_api/config.py",
        "scripts/release/runtime_config_contract.py",
        "Generated ENV_VARS_JSON support matrix",
        "Worker command:",
    ]:
        assert required in text


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


def test_browser_live_validation_checklist_authority_exists() -> None:
    """WS5 browser/live validation checklist must exist with gate contracts."""
    path = (
        DOCS_ROOT / "plan" / "release" / "BROWSER-LIVE-VALIDATION-CHECKLIST.md"
    )
    assert path.is_file()
    content = path.read_text(encoding="utf-8")

    for required in [
        "agent-browser",
        "ValidateDev",
        "ValidateProd",
        "/v1/transfers",
        "/v1/jobs",
        "browser-live-validation-report.schema.json",
    ]:
        assert required in content


def test_agents_active_authority_pack_has_final_split() -> None:
    """AGENTS authority list must include the final authority split."""
    text = AGENTS_PATH.read_text(encoding="utf-8")
    for required in [
        "ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md",
        "ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md",
        "ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md",
        "ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md",
        "ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md",
        "SPEC-0017-runtime-component-topology-and-ownership-contract.md",
        "SPEC-0018-runtime-configuration-and-startup-validation-contract.md",
        "SPEC-0019-auth-execution-and-threadpool-safety-contract.md",
        "SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md",
        "SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md",
        "SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md",
        "SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md",
        "SPEC-0024-cloudformation-module-contract.md",
        "SPEC-0025-reusable-workflow-integration-contract.md",
        "SPEC-0026-ci-cd-iam-least-privilege-matrix.md",
        "docs/standards/README.md",
        "ADR-0033-single-runtime-auth-authority.md",
        "SPEC-0027-public-http-contract-revision-and-bearer-auth.md",
        "bearer JWT",
        "uv run ruff check . --select I",
        "uv run ruff format . --check",
    ]:
        assert required in text


def test_agents_includes_typescript_sdk_operator_rules() -> None:
    """AGENTS must include the public TS SDK anti-regression rules."""
    text = AGENTS_PATH.read_text(encoding="utf-8")
    for required in [
        'must not expose package-root `"."` exports',
        "CodeArtifact staged/prod",
        "generator-owned and subpath-only",
        "x-nova-sdk-visibility: internal",
        "scripts/release/generate_clients.py",
        "docs/standards/README.md",
        "v2.9.5 or newer",
    ]:
        assert required in text


def test_agents_includes_workspace_packaging_and_docker_build_rules() -> None:
    """AGENTS must keep the current package and local image-build contract."""
    text = AGENTS_PATH.read_text(encoding="utf-8")
    for required in [
        "explicit intra-workspace runtime dependencies",
        "Do not rely on root workspace sync/install shape",
        "BuildKit plus `buildx`",
        "docker-buildx-and-credential-helper-setup-guide.md",
        "docker buildx version",
        "DOCKER_BUILDKIT=1 docker buildx build --load",
    ]:
        assert required in text


def test_authority_docs_reference_restored_runtime_set() -> None:
    """Authority docs must reference the restored runtime set."""
    for rel_path in [
        "docs/architecture/adr/index.md",
        "docs/architecture/spec/index.md",
        "docs/plan/PLAN.md",
        "docs/runbooks/README.md",
        "docs/PRD.md",
        "README.md",
    ]:
        text = _read(rel_path)
        for required in [
            "ADR-0025",
            "ADR-0026",
            "ADR-0027",
            "ADR-0028",
            "ADR-0029",
            "ADR-0033",
            "SPEC-0017",
            "SPEC-0018",
            "SPEC-0019",
            "SPEC-0020",
            "SPEC-0021",
            "SPEC-0022",
            "SPEC-0023",
            "SPEC-0027",
        ]:
            assert required in text, f"{rel_path} missing {required}"


def test_active_docs_do_not_reference_displaced_deploy_authority_paths() -> (
    None
):
    """Active docs must not keep the old deploy-governance filenames alive."""
    stale_paths = [
        "ADR-0025-reusable-workflow-api-and-versioning-policy.md",
        "ADR-0026-oidc-iam-role-partitioning-for-deploy-automation.md",
        "SPEC-0017-cloudformation-module-contract.md",
        "SPEC-0018-reusable-workflow-integration-contract.md",
        "SPEC-0019-ci-cd-iam-least-privilege-and-role-boundary-contract.md",
    ]

    violations: list[str] = []
    for doc in _markdown_targets(
        (
            REPO_ROOT / "README.md",
            REPO_ROOT / "AGENTS.md",
            DOCS_ROOT / "PRD.md",
            DOCS_ROOT / "plan" / "PLAN.md",
            DOCS_ROOT / "runbooks" / "README.md",
            DOCS_ROOT / "overview" / "NOVA-REPO-OVERVIEW.md",
            DOCS_ROOT / "clients" / "README.md",
            DOCS_ROOT / "standards",
            DOCS_ROOT / "architecture" / "adr",
            DOCS_ROOT / "architecture" / "spec",
        )
    ):
        text = doc.read_text(encoding="utf-8")
        for stale_path in stale_paths:
            if stale_path in text:
                if f"superseded/{stale_path}" in text:
                    continue
                violations.append(f"{doc.relative_to(REPO_ROOT)}: {stale_path}")

    assert not violations, (
        "Found stale authority paths in active docs:\n" + "\n".join(violations)
    )


def test_release_docs_align_validation_path_policy_contract() -> None:
    """Release docs must allow legacy 404 checks in validation assertions."""
    text = _read("docs/plan/release/config-values-reference-guide.md")
    for required in [
        "validation_legacy_404_paths",
        (
            "Legacy route literals are allowed only in dedicated "
            "validation `404` checks"
        ),
    ]:
        assert required in text


def test_auth0_and_ssm_contract_docs_reference_schema_authority() -> None:
    """Auth0 and SSM authority docs must reference active schema contracts."""
    auth0_runbook = _read("docs/plan/release/AUTH0-A0DEPLOY-RUNBOOK.md")
    contracts_readme = _read("docs/contracts/README.md")
    ssm_spec = _read(
        "docs/architecture/spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md"
    )

    for required in [
        "SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md",
        "workflow-auth0-tenant-ops-v1.schema.json",
    ]:
        assert required in auth0_runbook

    for required in [
        "workflow-auth0-tenant-ops-v1.schema.json",
        "ssm-runtime-base-url-v1.schema.json",
        "SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md",
        "SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md",
    ]:
        assert required in contracts_readme

    for required in [
        "/nova/dev/{service}/base-url",
        "/nova/prod/{service}/base-url",
    ]:
        assert required in ssm_spec


def test_release_docs_include_aws_cli_floor_for_codeartifact_npm_login() -> (
    None
):
    """Active runbooks must document the AWS CLI floor for npm 10.x."""
    for rel_path in [
        "docs/plan/release/RELEASE-RUNBOOK.md",
        "docs/plan/release/config-values-reference-guide.md",
        "docs/runbooks/README.md",
        "README.md",
    ]:
        text = _read(rel_path)
        assert "v2.9.5 or newer" in text, f"{rel_path} missing AWS CLI floor"
