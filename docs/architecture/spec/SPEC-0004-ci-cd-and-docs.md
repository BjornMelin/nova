---
Spec: 0004
Title: CI/CD and Documentation Automation
Status: Active
Version: 2.0
Date: 2026-04-02
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
- `npx aws-cdk@2.1117.0 synth --app "uv run --package nova-cdk python infra/nova_cdk/app.py" …`
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

## 2. Human GitHub plus AWS-native pipeline model

Canonical flow:

1. `ci.yml` validates runtime, generated-client, and conformance contracts on
   PR, merge queue, and main.
2. `release-plan.yml` remains a manual read-only entry wrapper on `main` and
   delegates to `reusable-release-plan.yml` to preview release-prep intent.
3. Human operators run `scripts.release.prepare_release_pr` locally, commit the
   generated `release/**` artifacts, and merge the resulting release PR
   through protected `main`.
4. AWS CodePipeline source action consumes merged `main` through an already
   provisioned `AVAILABLE` CodeConnections connection ARN.
5. AWS CodeBuild/buildspec release stages own package publication, immutable
   runtime artifact publication, release execution manifest writing, and runtime
   deployment.
6. AWS stages run:
   - `ValidateReleasePrep`
   - `PublishAndDeployDev`
   - `ApproveProd`
   - `PromoteAndDeployProd`

## 3. Selective release artifacts

Release-prep and release-execution artifacts MUST include:

- committed release-prep artifacts under `release/**`
- `api-lambda-artifact.json`
- `workflow-lambda-artifact.json`
- S3-backed release execution manifest JSON
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

The workflow Lambda artifact contract is:

- content-addressed S3 key:
  `runtime/nova-workflows/<release_commit_sha>/<artifact_sha256>/nova-workflows-lambda.zip`
- required manifest fields mirror the public API Lambda artifact contract
- the workflow ZIP is the only supported workflow-task deployment artifact; do
  not build or publish workflow-task container images in the canonical release
  path
- consumers MUST validate the manifest field set before use via
  `scripts/release/emit_workflow_lambda_artifact_env.py`
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
6. Release build publication consumes the committed release-prep artifacts from
   the merged release commit rather than recomputing selective release intent
   after the merge.

## 4. Protected-branch mutation rule

Release automation MUST NOT push commits to protected branches. Human-authored
release PRs carry the committed prep artifacts, and AWS builds the authoritative
post-merge execution manifest from the merged commit SHA.

Secrets policy:

- No static AWS access keys in GitHub secrets.
- GitHub-hosted workflows do not assume AWS release or deploy roles.
- Release signing material is read only by the AWS-native release control plane.

## 5. Build and exported variable contract

The release buildspecs under `infra/nova_cdk/buildspecs/` MUST enforce this
build contract:

1. Publish changed workspace package artifacts to CodeArtifact.
   - `twine upload` MUST target `--repository codeartifact`.
   - release-grade TypeScript package artifacts MUST be staged and promoted
     through CodeArtifact npm repositories.
   - R package artifacts MUST be built, checked, and stored as signed tarball
     evidence plus CodeArtifact generic packages.
2. Build the immutable public API Lambda ZIP and the immutable workflow Lambda
   ZIP from the merged release commit.
3. Produce deploy artifacts consumed by both Dev and Prod promotion stages.
4. Export build variables:
   - `PUBLISHED_PACKAGES`
   - `RELEASE_MANIFEST_SHA256`
   - `CHANGED_UNITS`

Required CodeBuild environment inputs:

- `CODEARTIFACT_DOMAIN`
- `CODEARTIFACT_STAGING_REPOSITORY` (build publish target / promotion source)
- `CODEARTIFACT_PROD_REPOSITORY` (promotion destination authority)
- `RELEASE_ARTIFACT_BUCKET`
- `RELEASE_MANIFEST_BUCKET`
- `RELEASE_SIGNING_SECRET_ID`
- `DEV_RUNTIME_STACK_ID`
- `DEV_RUNTIME_CFN_EXECUTION_ROLE_ARN`
- `DEV_RUNTIME_CONFIG_PARAMETER_NAME`
- `PROD_RUNTIME_STACK_ID`
- `PROD_RUNTIME_CFN_EXECUTION_ROLE_ARN`
- `PROD_RUNTIME_CONFIG_PARAMETER_NAME`

Default build target values:

- `DEV_RUNTIME_STACK_ID=NovaRuntimeStack`
- `PROD_RUNTIME_STACK_ID=NovaRuntimeProdStack`

Runtime artifact contract:

- The public API Lambda and workflow tasks are native ZIP packages built from
  repo-owned asset commands; neither surface is a release container image.

## 6. AWS promotion and deployment controls

Pipeline controls:

1. Dev and Prod are the only release environments.
2. Manual approval is mandatory before Prod deployment.
3. Prod promotion reuses immutable artifacts from Dev promotion; no rebuild.
4. CloudFormation execution roles are environment-scoped.
5. `iam:PassRole` permissions are constrained to deployment allowlists.

CodeConnections control:

- The release control plane imports an existing `AVAILABLE` connection ARN; it
  does not create a new CodeConnections resource as part of the Nova stack.

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
- committed `release/**` artifacts when those files change
- `docs/history/README.md` and any affected archive bundle links when archive
  paths or authority links change

## 9. Traceability

- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
