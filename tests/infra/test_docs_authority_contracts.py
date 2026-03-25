"""Documentation authority contract tests for Nova-path runbooks."""

from __future__ import annotations

import re
from pathlib import Path

from .helpers import REPO_ROOT
from .helpers import read_repo_file as _read

DOCS_ROOT = REPO_ROOT / "docs"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"

ACTIVE_DOCS_PATHS = (
    REPO_ROOT / "README.md",
    AGENTS_PATH,
    DOCS_ROOT / "README.md",
    DOCS_ROOT / "standards",
    DOCS_ROOT / "plan",
    DOCS_ROOT / "runbooks",
    DOCS_ROOT / "release",
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
    DOCS_ROOT / "runbooks" / "provisioning" / "config-values-reference.md"
)
RUNTIME_CONFIG_CONTRACT_DOC_PATH = (
    DOCS_ROOT / "release" / "runtime-config-contract.generated.md"
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


def _section(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    assert start != -1, f"Missing section marker: {start_marker}"
    end = text.find(end_marker, start)
    assert end != -1, f"Missing section terminator: {end_marker}"
    return text[start:end]


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

    for doc in _markdown_targets(ACTIVE_DOCS_PATHS):
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
                context = text[max(0, match.start() - 120) : match.start()]
                if "http" in context or "https" in context:
                    continue
                if "Do not add compatibility aliases" in context:
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
        DOCS_ROOT / "runbooks" / "provisioning" / "config-values-reference.md"
    ).read_text(encoding="utf-8")
    release_policy = (
        DOCS_ROOT / "runbooks" / "release" / "release-policy.md"
    ).read_text(encoding="utf-8")

    for required in [
        "CODEARTIFACT_DOMAIN",
        "CODEARTIFACT_STAGING_REPOSITORY",
        "CODEARTIFACT_PROD_REPOSITORY",
        "GITHUB_OWNER",
        "GITHUB_REPO",
        "publish-packages.yml",
        "promote-prod.yml",
        "runtime-config-contract.generated.md",
        "does not infer the target repository from the local checkout",
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
        DOCS_ROOT / "runbooks" / "release" / "release-runbook.md"
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
        DOCS_ROOT
        / "runbooks"
        / "release"
        / "browser-live-validation-checklist.md"
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
    """AGENTS must route readers to the canonical authority owners."""
    text = AGENTS_PATH.read_text(encoding="utf-8")
    for required in [
        "docs/architecture/README.md",
        "docs/standards/README.md",
        "docs/runbooks/README.md",
        "docs/contracts/README.md",
        "bearer JWT",
        "FILE_TRANSFER_CACHE_ENABLED=true",
        "CACHE_REDIS_URL",
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
        "NPM_CONFIG_USERCONFIG",
    ]:
        assert required in text


def test_agents_includes_workspace_packaging_and_docker_build_rules() -> None:
    """AGENTS must keep the current package and local image-build contract."""
    text = AGENTS_PATH.read_text(encoding="utf-8")
    for required in [
        "explicit intra-workspace runtime dependencies",
        "Do not rely on root workspace sync/install shape",
        "BuildKit plus `buildx`",
        "docker-buildx-credential-helper-setup.md",
        "docker buildx version",
        "DOCKER_BUILDKIT=1 docker buildx build --load",
    ]:
        assert required in text


def test_docs_router_separates_sdk_governance_from_downstream_consumers() -> (
    None
):
    """docs/README must not route SDK readers into downstream docs first."""
    text = _read("docs/README.md")
    for required in [
        "### SDK governance",
        "### Downstream consumer integration",
        "### Contract schemas",
        "./contracts/README.md",
        "./clients/README.md",
        "./architecture/spec/SPEC-0029-sdk-architecture-and-artifact-contract.md",
    ]:
        assert required in text


def test_architecture_router_owns_narrative_authority_map() -> None:
    """Architecture README must remain the narrative owner of active packs."""
    architecture_readme = _read("docs/architecture/README.md")
    adr_index = _read("docs/architecture/adr/index.md")
    spec_index = _read("docs/architecture/spec/index.md")

    for required in [
        "SPEC-0027-public-http-contract-revision-and-bearer-auth.md",
        "ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md",
        "ADR-0039-aws-target-platform.md",
        "SPEC-0024-cloudformation-module-contract.md",
        "SPEC-0025-reusable-workflow-integration-contract.md",
        "SPEC-0026-ci-cd-iam-least-privilege-matrix.md",
    ]:
        assert required in architecture_readme

    assert "This file is the ADR catalog and status index." in adr_index
    assert "This file is the SPEC catalog and status index." in spec_index


def test_requirements_defer_router_set_to_standards_doc() -> None:
    """requirements.md must not own a competing router-update list."""
    text = _read("docs/architecture/requirements.md")
    assert "repository-engineering-standards.md" in text
    assert "current canonical routers and any" in text


def test_active_docs_do_not_reference_repo_root_final_plan() -> None:
    """Active docs must not reference the removed repo-root FINAL-PLAN.md."""
    violations: list[str] = []
    for doc in _markdown_targets(
        (
            REPO_ROOT / "README.md",
            REPO_ROOT / "AGENTS.md",
            DOCS_ROOT,
        )
    ):
        if "history" in doc.parts or "superseded" in doc.parts:
            continue
        text = doc.read_text(encoding="utf-8")
        if "FINAL-PLAN.md" in text:
            violations.append(str(doc.relative_to(REPO_ROOT)))

    assert not violations, (
        "Found repo-root FINAL-PLAN.md references in active docs:\n"
        + "\n".join(violations)
    )


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
        "SPEC-0011-multi-language-sdk-architecture-and-package-map.md",
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
    text = _read("docs/runbooks/provisioning/config-values-reference.md")
    for required in [
        "validation_legacy_404_paths",
        (
            "Legacy route literals are allowed only in dedicated "
            "validation `404` checks"
        ),
    ]:
        assert required in text


def test_runtime_provisioning_docs_lock_cloudfront_ingress_contract() -> None:
    """Provisioning docs must keep CloudFront-managed ALB ingress canonical."""
    deploy_text = _read(
        "docs/runbooks/provisioning/deploy-runtime-cloudformation-environments.md"
    )
    required_inputs = _section(
        deploy_text,
        "## Required Inputs",
        "## Reproducible Deployment Sequence",
    )
    required_input_lines = [
        line.strip()
        for line in required_inputs.splitlines()
        if line.strip().startswith("- ")
    ]
    assert all("ALB_INGRESS_" not in line for line in required_input_lines)
    for required in [
        "validated internal ALB origin DNS used by the ALB certificate",
        "CloudFront origin TLS handshake",
        "Do not export `ALB_INGRESS_PREFIX_LIST_ID`, `ALB_INGRESS_CIDR`, or",
        "com.amazonaws.global.cloudfront.origin-facing",
    ]:
        assert required in required_inputs

    config_text = _read("docs/runbooks/provisioning/config-values-reference.md")
    runtime_values = _section(
        config_text,
        (
            "Capture and manage these runtime values per environment before "
            "CI/CD deploy:"
        ),
        "Retired runtime deploy inputs:",
    )
    runtime_value_lines = [
        line.strip()
        for line in runtime_values.splitlines()
        if line.strip().startswith("- ")
    ]
    assert all("ALB_INGRESS_" not in line for line in runtime_value_lines)
    for required in [
        "validated internal ALB origin DNS name used by the ALB certificate",
        "CloudFront origin TLS validation",
        "AlbIngressPrefixListId",
        "scripts/release/deploy-runtime-cloudformation-environment.sh",
    ]:
        assert required in runtime_values

    retired_inputs = _section(
        config_text,
        "Retired runtime deploy inputs:",
        "## CloudFormation stack names and outputs",
    )
    for retired in [
        "ALB_INGRESS_PREFIX_LIST_ID",
        "ALB_INGRESS_CIDR",
        "ALB_INGRESS_SOURCE_SG_ID",
    ]:
        assert retired in retired_inputs


def test_auth0_and_ssm_contract_docs_reference_schema_authority() -> None:
    """Auth0 and SSM authority docs must reference active schema contracts."""
    auth0_runbook = _read("docs/runbooks/release/auth0-a0deploy-runbook.md")
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
        "../architecture/requirements.md",
    ]:
        assert required in contracts_readme

    for required in [
        "/nova/dev/{service}/base-url",
        "/nova/prod/{service}/base-url",
    ]:
        assert required in ssm_spec


def test_release_docs_include_explicit_userconfig_npm_flow() -> None:
    """Active runbooks must document the explicit npm userconfig flow."""
    for rel_path in [
        "docs/runbooks/release/release-runbook.md",
        "docs/runbooks/provisioning/config-values-reference.md",
        "README.md",
    ]:
        text = _read(rel_path)
        assert "NPM_CONFIG_USERCONFIG" in text, (
            f"{rel_path} missing explicit npm userconfig guidance"
        )
        assert "NPM_REGISTRY_URL" in text, (
            f"{rel_path} missing explicit npm registry guidance"
        )


def test_clients_docs_use_immutable_reusable_workflow_refs() -> None:
    """Consumer docs/examples must not recommend mutable @v1 workflow pins."""
    violations: list[str] = []
    mutable_workflow_ref = re.compile(
        r"^\s*uses:\s+\S+@v1(?:\s|$)",
        re.MULTILINE,
    )
    for doc in (DOCS_ROOT / "clients").rglob("*"):
        if not doc.is_file() or doc.suffix not in {".md", ".yml"}:
            continue
        text = doc.read_text(encoding="utf-8")
        if mutable_workflow_ref.search(text):
            violations.append(str(doc.relative_to(REPO_ROOT)))

    assert not violations, (
        "Found mutable @v1 workflow refs in downstream consumer docs:\n"
        + "\n".join(sorted(violations))
    )


def test_overview_doc_remains_orientation_only() -> None:
    """Overview doc must not reintroduce stale callback/archive claims."""
    text = _read("docs/overview/NOVA-REPO-OVERVIEW.md")
    for forbidden in [
        "internal worker callback",
        "Worker callback",
        "FINAL-PLAN.md",
    ]:
        assert forbidden not in text


def test_release_promotion_doc_is_addendum_scoped() -> None:
    """Promotion guide must stay explicitly narrow-scoped."""
    text = _read("docs/runbooks/release/release-promotion-dev-to-prod.md")
    for required in [
        "addendum",
        "release-runbook.md",
        "release-policy.md",
        "Evidence Boundary",
    ]:
        assert required in text
