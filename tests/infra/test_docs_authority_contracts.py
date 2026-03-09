"""Documentation authority contract tests for Nova-path runbooks."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"

ACTIVE_DOCS_PATHS = (
    DOCS_ROOT / "runbooks",
    DOCS_ROOT / "plan" / "release",
    DOCS_ROOT / "architecture" / "adr",
    DOCS_ROOT / "architecture" / "spec",
)

SUPERSEDED_PARTS = {"superseded"}

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
    re.compile(r"/api(?:/|\*)"),
    re.compile(r"/healthz(?:\b|/)"),
    re.compile(r"/readyz(?:\b|/)"),
)

RETIRED_CONFORMANCE_CHECK_NAMES = (
    "dash-conformance",
    "shiny-conformance",
    "typescript-conformance",
)


def _markdown_files(base_path: Path) -> list[Path]:
    return sorted(
        path
        for path in base_path.rglob("*.md")
        if path.is_file() and not (set(path.parts) & SUPERSEDED_PARTS)
    )


def _markdown_targets(paths: tuple[Path, ...]) -> list[Path]:
    docs: list[Path] = []
    for path in paths:
        if path.is_file():
            docs.append(path)
        elif path.is_dir():
            docs.extend(_markdown_files(path))
    return sorted(docs)


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


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


def test_active_docs_do_not_use_workstream_batch_naming() -> None:
    """Active docs must use descriptive release-validation naming."""
    violations: set[str] = set()

    for doc in _markdown_targets(ACTIVE_ROUTE_AUTHORITY_PATHS):
        text = doc.read_text(encoding="utf-8")
        for term in ("Batch B", "BatchB", "batch-b"):
            if term in text:
                rel_path = doc.relative_to(REPO_ROOT)
                violations.add(f"{rel_path}: {term}")

    assert not violations, (
        "Found workstream batch naming in active docs:\n"
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
        "WORKFLOW_API_MAJOR",
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


def test_runtime_deploy_guide_uses_canonical_script() -> None:
    """Runtime deploy authority must point to the final convergence path."""
    text = _read(
        "docs/plan/release/deploy-runtime-cloudformation-environments-guide.md"
    )

    for required in [
        "scripts/release/deploy-runtime-cloudformation-environment.sh",
        "infra/runtime/file_transfer/s3.yml",
        "infra/runtime/file_transfer/async.yml",
        "infra/runtime/file_transfer/cache.yml",
        "infra/runtime/file_transfer/worker.yml",
        "AssignPublicIp=DISABLED",
        "IdempotencyMode=shared_required",
        "FileTransferCacheEnabled=true",
        "Do not reuse the CI artifact bucket as the file-transfer bucket.",
        "reusable-deploy-runtime.yml",
    ]:
        assert required in text

    for forbidden in [
        'AssignPublicIp="${ASSIGN_PUBLIC_IP:-DISABLED}"',
        'IdempotencyMode="${IDEMPOTENCY_MODE:-local_only}"',
        'FileTransferCacheEnabled="${FILE_TRANSFER_CACHE_ENABLED:-false}"',
    ]:
        assert forbidden not in text


def test_agents_active_authority_pack_includes_ws6_contracts() -> None:
    """AGENTS authority list must include active WS6 ADR/SPEC contracts."""
    text = AGENTS_PATH.read_text(encoding="utf-8")
    for required in [
        "ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md",
        "ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md",
        "ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md",
        "SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md",
        "SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md",
        "SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md",
        "/v1/token/verify",
        "/v1/token/introspect",
        "uv run ruff check . --select I",
        "uv run ruff format . --check",
    ]:
        assert required in text

    for required in [
        "docs/architecture/adr/superseded/**",
        "docs/architecture/spec/superseded/**",
    ]:
        assert required in text


def test_ws6_authority_docs_reference_new_contracts() -> None:
    """Authority indexes and runbooks must reference WS6 contract additions."""
    required_by_file = {
        "docs/architecture/adr/index.md": [
            "ADR-0027",
            "ADR-0028",
            "ADR-0029",
        ],
        "docs/architecture/spec/index.md": [
            "SPEC-0021",
            "SPEC-0022",
            "SPEC-0023",
        ],
        "docs/plan/PLAN.md": [
            "ADR-0027",
            "ADR-0028",
            "ADR-0029",
            "SPEC-0021",
            "SPEC-0022",
            "SPEC-0023",
        ],
        "docs/runbooks/README.md": [
            "ADR-0027",
            "ADR-0028",
            "ADR-0029",
            "SPEC-0021",
            "SPEC-0022",
            "SPEC-0023",
        ],
        "docs/PRD.md": [
            "ADR-0027",
            "ADR-0028",
            "ADR-0029",
            "SPEC-0021",
            "SPEC-0022",
            "SPEC-0023",
        ],
    }

    for rel_path, required_tokens in required_by_file.items():
        text = _read(rel_path)
        for required in required_tokens:
            assert required in text, f"{rel_path} missing {required}"


def test_active_authority_docs_reference_correct_spec_0020_identity() -> None:
    """Top-level docs must reference the repaired SPEC-0020 identity."""
    active_authority_docs = [
        "AGENTS.md",
        "docs/PRD.md",
        "docs/plan/PLAN.md",
        "docs/runbooks/README.md",
    ]

    for rel_path in active_authority_docs:
        text = _read(rel_path)
        assert (
            "SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md"
            in text
        )
        assert "Rollout and validation strategy" not in text


def test_spec_indexes_and_active_authority_specs_use_superseded_sections() -> (
    None
):
    """ADR/SPEC indexes must separate superseded authority from active docs."""
    adr_index = _read("docs/architecture/adr/index.md")
    spec_index = _read("docs/architecture/spec/index.md")
    spec_0020 = _read(
        "docs/architecture/spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md"
    )

    for required in [
        "## Superseded",
        "./superseded/ADR-0014-container-craft-capability-absorption-and-repo-retirement.md",
        "./superseded/ADR-0016-minimal-governance-final-state-operator-path.md",
    ]:
        assert required in adr_index

    for required in [
        "## Superseded",
        "./superseded/SPEC-0020-rollout-and-validation-strategy.md",
        (
            "Architecture authority pack and documentation "
            "synchronization contract"
        ),
    ]:
        assert required in spec_index

    assert "shared execution ledger" not in spec_0020
    assert "Rollout and validation strategy" not in spec_0020


def test_ci_cd_doc_contract_uses_dual_image_digests() -> None:
    """Active CI/CD spec must use the live dual-image digest contract."""
    text = _read("docs/architecture/spec/SPEC-0004-ci-cd-and-docs.md")

    for required in [
        "FILE_IMAGE_DIGEST",
        "AUTH_IMAGE_DIGEST",
        "RELEASE_MANIFEST_SHA256",
    ]:
        assert required in text

    assert "`IMAGE_DIGEST`" not in text
    assert "cross-framework conformance gate" not in text
    assert "generated-client conformance gate" in text


def test_release_docs_align_validation_path_policy_contract() -> None:
    """Release docs must allow legacy 404 checks only as validation assertions.

    Returns:
        None.
    """
    text = _read("docs/plan/release/config-values-reference-guide.md")
    for required in [
        "validation_legacy_404_paths",
        (
            "Legacy route literals are allowed only in dedicated "
            "validation `404` checks"
        ),
    ]:
        assert required in text


def test_release_config_values_distinguish_artifact_and_transfer_buckets() -> (
    None
):
    """Release config authority must keep CI and runtime buckets distinct."""
    text = _read("docs/plan/release/config-values-reference-guide.md")

    for required in [
        "NOVA_ARTIFACT_BUCKET_NAME` is CI/CD storage",
        "It is not the runtime upload/download bucket.",
        "FILE_TRANSFER_BUCKET_BASE_NAME",
        "deploy-runtime-cloudformation-environment.sh",
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
        "workflow-auth0-tenant-deploy.schema.json",
        "@v1",
        "@v1.x.y",
    ]:
        assert required in auth0_runbook

    for required in [
        "workflow-auth0-tenant-deploy.schema.json",
        "ssm-runtime-base-url-v1.schema.json",
        "SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md",
        "SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md",
        "@v1",
        "@v1.x.y",
    ]:
        assert required in contracts_readme

    for required in [
        "/nova/dev/{service}/base-url",
        "/nova/prod/{service}/base-url",
    ]:
        assert required in ssm_spec


def test_release_docs_define_reusable_workflow_versioning_policy() -> None:
    """Release docs must define major-tag and immutable-pin workflow policy."""
    release_policy = _read("docs/plan/release/RELEASE-POLICY.md")
    release_runbook = _read("docs/plan/release/RELEASE-RUNBOOK.md")
    clients_readme = _read("docs/clients/README.md")

    for required in [
        "v1.x.y",
        "v1` points to the latest compatible",
        "production and",
        "high-assurance guidance requires",
        "`@v1.x.y` or a full commit SHA",
        "Composite actions under `.github/actions/**` are internal",
        "published as direct external APIs",
    ]:
        assert required in release_policy

    for required in [
        "Publish reusable workflow tags",
        "v1.2.3",
        "v2.0.0",
        "moving major tag (`v1`)",
        "WORKFLOW_API_MAJOR",
    ]:
        assert required in release_runbook

    for required in [
        "`@v1` is the public compatibility channel",
        "immutable release tags such as",
        "`@v1.x.y`",
        "full",
        "commit SHA",
    ]:
        assert required in clients_readme
