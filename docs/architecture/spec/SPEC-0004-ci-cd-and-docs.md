---
Spec: 0004
Title: CI/CD and Documentation Automation
Status: Active
Version: 1.8
Date: 2026-03-18
Related:
  - "[ADR-0002: OpenAPI as contract and SDK generation](../adr/ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](../adr/ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](../adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
  - "[ADR-0023: Hard cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[ADR-0012: No Lambda runtime scope](../adr/ADR-0012-no-lambda-runtime-scope.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: v1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[SPEC-0025: Reusable workflow integration contract](./SPEC-0025-reusable-workflow-integration-contract.md)"
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
- unified `Nova CI` workflow gate (`.github/workflows/ci.yml`) covering:
  - `dash-conformance`
  - `shiny-conformance`
  - `typescript-conformance` (release-grade TypeScript SDK client + fixture
    smoke; required check name remains stable)
  - `generated-clients`

Release workflows also carry the first-class internal R release line via
package build/check and signed tarball evidence. Those validations remain in
release automation rather than protected-branch required checks.

Protected branch wiring details are documented in
`docs/runbooks/release/governance-lock-and-branch-protection.md`.

Required-check workflows MUST always trigger on pull requests to `main` branch
protection. Minute reduction is enforced with an initial classifier job and
job-level `if:` guards, not workflow-level path filters that leave required
checks pending.

## 2. Hybrid pipeline model

Canonical flow:

1. `ci.yml` validates runtime, generated-client, and conformance contracts on
   PR, merge queue, and main.
2. `release-plan.yml` is a manual entry wrapper on `main` and delegates to
   `reusable-release-plan.yml` to compute `changed-units.json` and
   `version-plan.json`.
3. `release-apply.yml` is a manual `main`-only entry wrapper and delegates to
   `reusable-release-apply.yml`.
4. `publish-packages.yml` is a manual `main`-only staged publish gate that
   consumes immutable `release-apply` artifacts from an explicit
   `release_apply_run_id`.
5. `reusable-release-apply.yml` applies selective versions, writes release
   manifest,
   updates `uv.lock`, and commits signed release metadata from `main` only.
6. AWS CodePipeline source action consumes signed commit through CodeConnections.
7. AWS CodeBuild/buildspec release stages own container image build/push
   authority; GitHub does not carry a separate image-wrapper workflow.
8. AWS stages run:
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
- `docs/release/RELEASE-VERSION-MANIFEST.md`
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
   - release-grade TypeScript package artifacts MUST be staged and promoted
     through CodeArtifact npm repositories.
   - R package artifacts MUST be built, checked, and stored as signed tarball
     evidence plus CodeArtifact generic packages.
2. Build and push container image artifacts and export immutable digest.
3. Produce deploy artifacts consumed by both Dev and Prod promotion stages.
4. Export build variables:
   - `FILE_IMAGE_DIGEST`
   - `PUBLISHED_PACKAGES`
   - `RELEASE_MANIFEST_SHA256`
   - `CHANGED_UNITS`

Required CodeBuild environment inputs:

- `CODEARTIFACT_DOMAIN`
- `CODEARTIFACT_STAGING_REPOSITORY` (build publish target / promotion source)
- `CODEARTIFACT_PROD_REPOSITORY` (promotion destination authority)
- `ECR_REPOSITORY_URI` or `ECR_REPOSITORY_NAME`

Default build target values:

- `FILE_DOCKERFILE_PATH=apps/nova_file_api_service/Dockerfile`
- `DOCKER_BUILD_CONTEXT=.`
- `DOCKER_BUILDKIT=1`
- Docker CLI with `buildx` available in the release-build environment

Release-image Dockerfile contract:

- Service Dockerfiles remain under `apps/*`; do not move them into workspace
  package paths.
- Service image builds MUST run with Docker BuildKit enabled.
- Service image builds MUST target the repo-approved Python `3.13-slim`
  baseline and use pinned `uv` for reproducible dependency installation.
- Service Dockerfiles MUST use exec-form single-process `uvicorn` commands and
  may not add `gunicorn` or in-container worker fan-out for the ECS/Fargate API
  services.

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

Any behavioral or contract change MUST update all affected docs in the same PR. In
particular, whenever CI/CD or release semantics change, the same PR MUST update
all affected operational docs:

- `README.md`
- `docs/PRD.md`
- `docs/architecture/requirements.md`
- affected ADR/SPEC docs
- `docs/plan/PLAN.md`
- affected `docs/contracts/*.json` workflow/artifact schemas
- affected `docs/clients/*.md` and `docs/clients/**/*.yml` when downstream
  integration contracts change
- `docs/runbooks/README.md` when runbook authority is changed
- `docs/history/README.md` and any affected archive bundle links when archive
  paths or authority links change
- `docs/runbooks/release/**` and `docs/runbooks/provisioning/**` runbooks and
  policy docs, plus committed `docs/release/**` artifacts when those files
  change
- `docs/history/**` when archival paths or evidence pointers change

## 9. Traceability

- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
