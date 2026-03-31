---
Spec: 0004
Title: CI/CD and Documentation Automation
Status: Active
Version: 1.9
Date: 2026-03-24
Related:
  - "[ADR-0002: OpenAPI as contract and SDK generation](../adr/ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[ADR-0011: Hybrid CI/CD with GitHub and AWS promotion](../adr/ADR-0011-cicd-hybrid-github-aws-promotion.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](../adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
  - "[ADR-0033: Canonical serverless platform](../adr/ADR-0033-canonical-serverless-platform.md)"
  - "[ADR-0023: Hard cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0016: v1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0029: Canonical serverless platform](./SPEC-0029-platform-serverless.md)"
  - "[requirements.md](../requirements.md)"
  - "[SPEC-0025: Reusable workflow integration contract](./SPEC-0025-reusable-workflow-integration-contract.md)"
  - "[SPEC-0031: Docs and tests authority reset](./SPEC-0031-docs-and-tests-authority-reset.md)"
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

Protected-branch CI and operator docs MUST keep the canonical baseline current.
Changes MUST pass the applicable baseline checks plus any touched-surface
add-on gates from `AGENTS.md` and
`docs/standards/repository-engineering-standards.md`.

Canonical baseline:

- `uv sync --locked --all-packages --all-extras --dev`
- `uv lock --check`
- `uv run ruff check .`
- `uv run ruff check . --select I`
- `uv run ruff format . --check`
- `uv run ty check --force-exclude --error-on-warning packages scripts`
- `uv run mypy`
- `uv run pytest -q -m runtime_gate`
- `uv run pytest -q -m "not runtime_gate and not generated_smoke"`
- `uv run pytest -q -m generated_smoke`
- `uv run python scripts/contracts/export_openapi.py --check`
- `uv run python scripts/release/generate_runtime_config_contract.py --check`
- `uv run python scripts/release/generate_clients.py --check`
- `uv run python scripts/release/generate_python_clients.py --check`
- `npx aws-cdk@2.1107.0 synth --app "uv run --package nova-cdk python infra/nova_cdk/app.py" …`
- workspace package/app build verification (`uv build` per workspace unit)
- unified `Nova CI` workflow gate (`.github/workflows/ci.yml`) covering:
  - `quality-gates` (Python 3.13 primary lane)
  - `python-compatibility` (Python 3.11 and 3.12 pytest/build lane)
  - `generated-clients`
  - `dash-conformance`
  - `shiny-conformance`
  - `typescript-conformance` (release-grade TypeScript SDK client + fixture
    smoke; required check name remains stable)
- separate `CFN Contract Validate` workflow gate

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
   manifest, updates `uv.lock`, creates a signed release commit from `main`
   only, builds the public API Lambda zip from that exact local signed commit,
   pushes the signed release commit to `main`, then uploads that zip plus
   `api-lambda-artifact.json` to `RELEASE_ARTIFACT_BUCKET` before artifact
   publication completes.
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
- `api-lambda-artifact.json`
- immutable deploy artifacts consumed by both Dev and Prod stages

The public API Lambda artifact contract is:

- content-addressed S3 key:
  `runtime/nova-file-api/<release_commit_sha>/<artifact_sha256>/nova-file-api-lambda.zip`
- required manifest fields:
  `release_commit_sha`, `package_name`, `package_version`, `runtime`,
  `architecture`, `artifact_bucket`, `artifact_key`, `artifact_sha256`,
  `built_at`
- no dependency on S3 object versioning
- consumers MUST validate the manifest field set before use via
  `scripts/release/emit_api_lambda_artifact_env.py`
- consumers MUST verify `artifact_sha256` against the downloaded zip bytes
  before treating the manifest as authoritative

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
2. Build and push workflow-task container image artifacts, excluding the public
   API Lambda native zip artifact, and export immutable digest when applicable.
3. Produce deploy artifacts consumed by both Dev and Prod promotion stages.
4. Export build variables:
   - `FILE_IMAGE_DIGEST` (only when a workflow-task image is part of the release)
   - `PUBLISHED_PACKAGES`
   - `RELEASE_MANIFEST_SHA256`
   - `CHANGED_UNITS`

Required CodeBuild environment inputs:

- `CODEARTIFACT_DOMAIN`
- `CODEARTIFACT_STAGING_REPOSITORY` (build publish target / promotion source)
- `CODEARTIFACT_PROD_REPOSITORY` (promotion destination authority)
- `ECR_REPOSITORY_URI` or `ECR_REPOSITORY_NAME` when a workflow-task image build is required

Default build target values:

- `FILE_DOCKERFILE_PATH=apps/nova_workflows_tasks/Dockerfile`
- `DOCKER_BUILD_CONTEXT=.`
- `DOCKER_BUILDKIT=1`
- Docker CLI with `buildx` available in the release-build environment

Workflow-task container image Dockerfile contract:

- Workflow-task Dockerfiles stay under `apps/*`; do not move them
  into workspace package paths.
- Workflow-task image builds MUST run with Docker BuildKit enabled.
- Workflow-task image builds MUST target the AWS Lambda Python 3.13 base image
  and use pinned `uv` for reproducible dependency installation.

Public API Lambda artifact contract:

- The public API Lambda is a native zip package built from a repo-owned custom
  asset command; it is not a release container image.

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
- `docs/README.md`
- `docs/PRD.md`
- `docs/architecture/README.md`
- `docs/architecture/requirements.md`
- affected ADR/SPEC docs and both architecture indexes
- `docs/standards/README.md`
- `docs/standards/repository-engineering-standards.md`
- `docs/contracts/README.md` and affected `docs/contracts/**` schemas
- affected `docs/clients/**` docs or workflow examples when downstream
  integration contracts change
- `docs/plan/PLAN.md`
- `docs/runbooks/README.md` when runbook authority is changed
- `docs/runbooks/release/**` and `docs/runbooks/provisioning/**` when release,
  deploy, or validation behavior changes
- committed `docs/release/**` artifacts when those files change
- `docs/history/README.md` and any affected archive bundle links when archive
  paths or authority links change

## 9. Traceability

- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
