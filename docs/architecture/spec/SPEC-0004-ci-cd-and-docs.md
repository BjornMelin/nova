---
Spec: 0004
Title: CI/CD and documentation automation
Status: Active
Version: 2.1
Date: 2026-03-06
Related:
  - "[ADR-0002: OpenAPI as contract and SDK generation](../adr/ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](../adr/ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[SPEC-0020: Architecture authority pack and documentation synchronization contract](./SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)"
  - "[SPEC-0024: CloudFormation module contract](./SPEC-0024-cloudformation-module-contract.md)"
  - "[SPEC-0025: Reusable workflow integration contract](./SPEC-0025-reusable-workflow-integration-contract.md)"
  - "[SPEC-0026: CI/CD IAM least-privilege matrix](./SPEC-0026-ci-cd-iam-least-privilege-matrix.md)"
References:
  - "[GitHub Actions](https://docs.github.com/actions)"
  - "[GitHub commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification)"
  - "[CodeBuild buildspec reference](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html)"
  - "[CodeConnections CloudFormation resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-codeconnections-connection.html)"
  - "[uv lock and sync behavior](https://github.com/astral-sh/uv/blob/main/docs/concepts/projects/sync.md)"
---

## 1. Scope

Defines the repository-level CI quality gates, immutable release-artifact
contract, and documentation-update obligations for Nova. Detailed deploy
control-plane, reusable workflow API, and IAM partitioning behavior is governed
by `SPEC-0024`, `SPEC-0025`, and `SPEC-0026`.

## 2. Required quality gates

Every pull request MUST pass:

- `source .venv/bin/activate && uv lock --check`
- `source .venv/bin/activate && uv run ruff check .`
- `source .venv/bin/activate && uv run ruff check . --select I`
- `source .venv/bin/activate && uv run ruff format . --check`
- `source .venv/bin/activate && uv run mypy`
- `source .venv/bin/activate && uv run pytest -q`
- `source .venv/bin/activate && uv run pytest -q packages/nova_file_api/tests/test_generated_client_smoke.py`
- `source .venv/bin/activate && uv run python scripts/contracts/export_openapi.py --check`
- `source .venv/bin/activate && uv run python scripts/release/generate_clients.py --check`
- `source .venv/bin/activate && uv run python scripts/release/generate_python_clients.py --check`
- workspace package/app build verification (`uv build` per workspace unit)
- generated-client conformance gate (`.github/workflows/conformance-clients.yml`)

## 3. Release-plan and release-apply artifact contract

Release-plan and release-apply flows MUST use immutable upstream artifacts:

- `changed-units.json`
- `version-plan.json`
- `docs/plan/release/RELEASE-VERSION-MANIFEST.md`
- `release-plan-artifacts`
- `release-apply-artifacts`

Rules:

1. `release-plan` is the only workflow allowed to compute `changed-units.json`
   and `version-plan.json`.
2. `release-apply`, `publish-packages`, and promotion workflows MUST consume
   upstream immutable artifacts and must not recompute release scope locally.
3. Release commits and release manifests are authored from the signed release
   path only.
4. GitHub Actions artifact downloads MUST resolve upstream artifacts by exact
   artifact `name`, paginate listing lookup until exhaustion, and fail closed
   when multiple active artifacts share the requested name for the same run.

## 4. Build export contract

`buildspec-release.yml` MUST export the current build variables used by the live
pipeline:

- `FILE_IMAGE_DIGEST`
- `AUTH_IMAGE_DIGEST`
- `PUBLISHED_PACKAGES`
- `RELEASE_MANIFEST_SHA256`
- `CHANGED_UNITS`

`RELEASE_MANIFEST_SHA256` is the SHA256 digest of
`docs/plan/release/RELEASE-VERSION-MANIFEST.md`, not of deploy-evidence
artifacts.

## 5. Signed release commit contract

Release-automation commits MUST:

1. retrieve signing material from AWS Secrets Manager via OIDC-assumed role
2. configure Git SSH signing in workflow runtime
3. create signed release commits
4. pass signature-verification workflow checks before release branch-protection
   requirements are satisfied

## 6. Documentation synchronization contract

Changes to CI/CD, release, reusable workflow, or deployment semantics MUST
update in the same change:

- `AGENTS.md`
- `docs/PRD.md`
- `docs/architecture/requirements.md`
- affected ADR/SPEC files
- `docs/plan/PLAN.md`
- affected `docs/contracts/*.json`
- affected `docs/clients/**`
- affected `docs/plan/release/**`

Historical pointer files (`PRD.md`, `FINAL-PLAN.md`) are updated only when
archive paths or authority links change.

## 7. Public SDK governance note

Python is the only release-grade public SDK surface in this wave. TypeScript
and R conformance lanes remain required internal generated-catalog drift gates,
not public release guarantees. The generated-client conformance workflow MUST
verify canonical OpenAPI export drift, internal TS/R generated catalogs, and
committed Python SDK package trees.

## 8. Acceptance criteria

1. Workflow wrappers remain thin and delegate shared behavior to reusable
   workflows or composite actions.
2. Release and publish workflows consume immutable upstream artifacts only.
3. Active docs use the current dual-image-digest and release-manifest-digest
   terminology.
4. Repo quality-gate and conformance checks stay synchronized with the
   documented contract.

## 9. Traceability

- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
