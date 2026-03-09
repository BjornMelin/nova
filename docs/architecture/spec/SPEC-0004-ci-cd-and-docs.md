---
Spec: 0004
Title: CI/CD and Documentation Automation
Status: Active
Version: 1.7
Date: 2026-03-05
Related:
  - "[ADR-0002: OpenAPI as contract and SDK generation](../adr/ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](../adr/ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[ADR-0025: Runtime monorepo component boundaries and ownership](../adr/ADR-0025-reusable-workflow-api-and-versioning-policy.md)"
  - "[ADR-0026: Fail-fast runtime configuration and safe auth execution](../adr/ADR-0026-oidc-iam-role-partitioning-for-deploy-automation.md)"
  - "[ADR-0023: Hard cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[ADR-0012: No Lambda runtime scope](../adr/ADR-0012-no-lambda-runtime-scope.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: v1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[SPEC-0018: Runtime configuration and startup validation contract](./SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[SPEC-0020: Architecture authority pack and documentation synchronization contract](./SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)"
References:
  - "[GitHub Actions](https://docs.github.com/actions)"
  - "[GitHub commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification)"
  - "[CodePipeline manual approvals](https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-action-add.html)"
  - "[CodePipeline approval IAM scoping](https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-iam-permissions.html)"
  - "[CodeConnections CloudFormation resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-codeconnections-connection.html)"
  - "[CodeBuild buildspec reference](https://docs.aws.amazon.com/codebuild/latest/userguide/build-spec-ref.html)"
  - "[CodeArtifact package groups](https://docs.aws.amazon.com/codeartifact/latest/ug/package-groups.html)"
  - "[CodeArtifact package group origin controls](https://docs.aws.amazon.com/codeartifact/latest/ug/package-group-origin-controls.html)"
  - "[uv lock and sync behavior](https://github.com/astral-sh/uv/blob/main/docs/concepts/projects/sync.md)"
---

## 1. Required quality gates

Every pull request MUST pass:

- `source .venv/bin/activate && uv lock --check`
- `source .venv/bin/activate && uv run ruff check .`
- `source .venv/bin/activate && uv run ruff check . --select I`
- `source .venv/bin/activate && uv run ruff format . --check`
- `source .venv/bin/activate && uv run mypy`
- `source .venv/bin/activate && uv run pytest -q`
- `source .venv/bin/activate && uv run pytest -q packages/nova_file_api/tests/test_generated_client_smoke.py`
- workspace package/app build verification (`uv build` per workspace unit)
- cross-framework conformance gate (`.github/workflows/conformance-clients.yml`):
  - `dash-conformance`
  - `shiny-conformance`
  - `typescript-conformance`

Protected branch wiring details are documented in
`docs/plan/release/branch-protection-required-checks.md`.

## 2. Hybrid pipeline model

Canonical flow:

1. `ci.yml` validates code and contracts on PR and main.
2. `release-plan.yml` is the entry wrapper and delegates to
   `reusable-release-plan.yml` to compute `changed-units.json` and
   `version-plan.json`.
3. `release-apply.yml` and `build-and-publish-image.yml` are entry wrappers
   and delegate to `reusable-release-apply.yml`.
4. `reusable-release-apply.yml` applies selective versions, writes release
   manifest,
   updates `uv.lock`, and commits signed release metadata from `main` only.
   For `workflow_run`, checkout is pinned to `workflow_run.head_sha`.
5. AWS CodePipeline source action consumes signed commit through CodeConnections.
6. AWS stages run:
   - Build release artifacts
   - Deploy Dev
   - Validate Dev
   - Manual approval
   - Deploy Prod
   - Validate Prod

## 3. Selective release artifacts

Release artifacts MUST include:

- `changed-units.json`
- `version-plan.json`
- `docs/plan/release/RELEASE-VERSION-MANIFEST.md`
- immutable deploy artifacts consumed by both Dev and Prod stages

Rules:

1. Changed unit detection is path-based by workspace unit roots.
2. First release baseline is full-unit release.
3. Subsequent baseline is the last commit touching release manifest on main.
4. Bump policy:
   - `BREAKING CHANGE` or `!` => major
   - `feat` => minor
   - all other commit types => patch
5. Dependent local workspace units receive patch bumps when dependency interface
   changes (major/minor source bump).
6. Release build publication resolves package paths from signed release commit
   parent diff (`HEAD^..HEAD`) to prevent empty publish sets on manifest-touching
   release commits.

## 4. Signed release commits

Release-automation commits MUST:

1. Retrieve signing material from AWS Secrets Manager via OIDC-assumed role.
2. Configure Git SSH signing (`gpg.format=ssh`) in workflow runtime.
3. Create release commit with `git commit -S`.
4. Be verified by `verify-signature.yml` before release branch protection is
   considered satisfied.

Secrets policy:

- No static AWS access keys in GitHub secrets.
- OIDC trust policies MUST constrain `aud=sts.amazonaws.com` and scoped `sub`
  claims for approved repo/branch patterns.

## 5. Build and exported variable contract

`buildspec-release.yml` MUST enforce this build contract:

1. Publish changed workspace package artifacts to CodeArtifact.
   - `twine upload` MUST target `--repository codeartifact`.
2. Build and push container image artifacts and export immutable digest.
3. Produce deploy artifacts consumed by both Dev and Prod promotion stages.
4. Export build variables:
   - `IMAGE_DIGEST`
   - `PUBLISHED_PACKAGES`
   - `RELEASE_MANIFEST_SHA256`
   - `CHANGED_UNITS`

Required CodeBuild environment inputs:

- `CODEARTIFACT_DOMAIN`
- `CODEARTIFACT_REPOSITORY`
- `ECR_REPOSITORY_URI` or `ECR_REPOSITORY_NAME`

Default build target values:

- `DOCKERFILE_PATH=apps/nova_file_api_service/Dockerfile`
- `DOCKER_BUILD_CONTEXT=.`

## 6. AWS promotion and deployment controls

Pipeline controls:

1. Dev and Prod are the only release environments.
2. Manual approval is mandatory before Prod deployment.
3. Prod promotion reuses immutable artifacts from Dev promotion; no rebuild.
4. CloudFormation execution roles are environment-scoped.
5. `iam:PassRole` permissions are constrained to deployment allowlists.

CodeConnections control:

- When a new connection is created by CloudFormation, the operator MUST perform
  one-time console activation from `PENDING` to `AVAILABLE`.

## 7. CodeArtifact hardening controls

CodeArtifact repository policy and package-group controls MUST enforce:

1. Internal namespace package groups with origin controls.
2. `EXTERNAL_UPSTREAM = BLOCK` for protected internal package groups.
3. `PUBLISH = ALLOW_SPECIFIC_REPOSITORIES` only for approved repositories.
4. Public upstream ingress only through approved upstream repo path.
5. Promotion IAM scopes MUST be explicit and directional:
   - `codeartifact:ReadFromRepository` on staged source repository only.
   - `codeartifact:CopyPackageVersions` on prod destination repository and
     required package resources only.

## 8. Documentation and traceability gates

The same PR MUST update affected operational docs whenever CI/CD or release
semantics change:

- `README.md`
- `docs/PRD.md`
- `docs/architecture/requirements.md`
- affected ADR/SPEC docs
- `docs/plan/PLAN.md`
- affected `docs/contracts/*.json` workflow/artifact schemas
- affected `docs/clients/*.md` and `docs/clients/**/*.yml` when downstream
  integration contracts change
- `PRD.md` and `FINAL-PLAN.md` pointers when archive paths or authority links
  change
- `docs/plan/release/*` runbooks and policy docs

## 9. Traceability

- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
