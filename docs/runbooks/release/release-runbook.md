# Release Runbook

Status: Active
Owner: nova release architecture
Last updated: 2026-04-02

## 1. Purpose

Execute the canonical Nova release flow: selective version planning, human
release-prep PR creation, AWS-native post-merge publish/promote/deploy, and
provenance-bound runtime validation.

## 1A. Authority / references

1. `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
2. `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
3. `docs/architecture/spec/SPEC-0004-ci-cd-and-docs.md`
4. `docs/architecture/spec/SPEC-0025-reusable-workflow-integration-contract.md`
5. `docs/contracts/deploy-output-authority-v2.schema.json`
6. `docs/contracts/release-prep-v1.schema.json`
7. `docs/contracts/release-execution-manifest-v1.schema.json`
8. `docs/contracts/workflow-post-deploy-validate.schema.json`
9. `infra/nova_cdk/README.md`

## 2. Preconditions

1. `main` is green on the required hosted checks in
   `governance-lock-and-branch-protection.md`.
2. The `NovaReleaseControlPlaneStack` is deployed in the target AWS account.
3. Either:
   - `NovaReleaseSupportStack` is deployed in the same account and provides the
     canonical dev/prod CloudFormation execution roles, or
   - explicit `DEV_RUNTIME_CFN_EXECUTION_ROLE_ARN` and
     `PROD_RUNTIME_CFN_EXECUTION_ROLE_ARN` values are supplied to the release
     control plane.
4. The configured `RELEASE_CONNECTION_ARN` already exists and is
   `AVAILABLE`.
5. Staging and prod CodeArtifact repositories already exist and are distinct.
6. Release control plane configuration exists for:
   - `RELEASE_CONNECTION_ARN`
   - `CODEARTIFACT_DOMAIN`
   - `CODEARTIFACT_STAGING_REPOSITORY`
   - `CODEARTIFACT_PROD_REPOSITORY`
   - `RELEASE_SIGNING_SECRET_ID`
   - `DEV_RUNTIME_STACK_ID`
   - `DEV_RUNTIME_CFN_EXECUTION_ROLE_ARN`
   - `DEV_RUNTIME_CONFIG_PARAMETER_NAME`
   - `PROD_RUNTIME_STACK_ID`
   - `PROD_RUNTIME_CFN_EXECUTION_ROLE_ARN`
   - `PROD_RUNTIME_CONFIG_PARAMETER_NAME`
7. If the first `api-nova` production cutover is using temporary wildcard CORS,
   GitHub issue `#111` remains open until the prod allowlist is tightened.

## 2A. Canonical local verification commands

- `uv sync --locked --all-packages --all-extras --dev`
- `uv run pytest -q -m runtime_gate`
- `uv run pytest -q -m "not runtime_gate and not generated_smoke"`
- `uv run pytest -q -m generated_smoke`
- `npx aws-cdk@2.1107.0 synth --app "uv run --package nova-cdk python infra/nova_cdk/app.py" …`

Do not treat a monolithic `uv run pytest -q` invocation or deleted GitHub
executor workflows as the canonical Nova verification shape.

## 3. Canonical release execution

### A. Plan

1. Trigger `Nova Release Plan` from `main`.
2. Confirm artifacts:
   - `changed-units.json`
   - `version-plan.json`

### B. Prepare the release PR locally

1. From a local checkout rooted on up-to-date `main`, run:

   ```bash
   uv run python -m scripts.release.prepare_release_pr --repo-root .
   ```

2. Confirm the command:
   - applies planned version bumps in tracked package manifests
   - refreshes `uv.lock`
   - writes `release/RELEASE-PREP.json`
   - writes `release/RELEASE-VERSION-MANIFEST.md`
3. Commit those changes on a normal branch and open a normal human-authored PR.
4. Merge through the existing protected `main` process.

### C. AWS-native post-merge execution

1. Confirm CodePipeline starts from the merged release commit SHA.
2. Confirm the stages run in this order:
   - `Source`
   - `ValidateReleasePrep`
   - `PublishAndDeployDev`
   - `ApproveProd`
   - `PromoteAndDeployProd`
3. Confirm the release-control-plane stack either imported explicit
   CloudFormation execution role ARNs or synthesized `NovaReleaseSupportStack`
   and wired those role outputs into the pipeline environment.
4. Confirm the dev stage:
   - validates `release/RELEASE-PREP.json`
   - publishes only to `CODEARTIFACT_STAGING_REPOSITORY`
   - builds the immutable API Lambda zip
   - builds the immutable workflow Lambda zip
   - uploads both immutable runtime artifacts to the release artifact bucket
   - writes the S3-backed `release-execution-manifest.json`
   - deploys the runtime from that exact artifact identity
5. Confirm the prod stage:
   - reuses the stored release execution manifest
   - promotes staged packages to `CODEARTIFACT_PROD_REPOSITORY`
   - deploys the runtime from the exact approved artifact coordinates
   - may temporarily deploy `allowed_origins=["*"]` for the first production
     custom-domain cutover only; issue `#111` tracks the required follow-up
     hardening

### D. Re-run post-deploy runtime validation when needed

1. Trigger `Post Deploy Validate` when you need to revalidate an existing
   deploy-output artifact.
2. Supply one deploy-output source:
   - `deploy_run_id`
   - `deploy_output_json`
   - `deploy_output_path`
3. Confirm `validation_status=passed` and retain the uploaded
   `post-deploy-validation-report` artifact.
4. Confirm the report proves health, protected auth behavior, browser CORS
   preflight, execute-api disablement, and legacy-path 404 drift against the
   canonical public base URL. The literal `browser CORS preflight` assertion
   remains part of the release-validation contract.

## 4. Evidence capture

Capture durable pointers for:

1. `Nova Release Plan` workflow run
2. Release PR URL and merge commit SHA
3. CodePipeline execution id for the merged release commit
4. CodeBuild execution ids for staging and prod
5. `Post Deploy Validate` workflow run when used
6. `release/RELEASE-VERSION-MANIFEST.md` SHA continuity through publish and promotion
7. Gate validation artifacts:
   - `codeartifact-gate-report.json`
   - `codeartifact-promotion-candidates.json`
8. API deploy artifact evidence:
   - `api-lambda-artifact.json`
   - `workflow-lambda-artifact.json`
   - `release-execution-manifest.json`
   - S3 key under
     `runtime/nova-file-api/<release_commit_sha>/<artifact_sha256>/nova-file-api-lambda.zip`
9. Runtime deploy authority evidence:
   - `deploy-output.json`
   - `deploy-output.sha256`
   - `post-deploy-validation-report.json`

## 5. Rollback guidance

1. If release-prep validation fails, fix the release PR and merge a new human
   release-prep commit; do not bypass the prep-artifact contract.
2. If staging publish or dev deploy fails, fix forward from `main` and allow a
   new CodePipeline execution to build a fresh release manifest.
3. If prod promotion fails, fix the staged payload or IAM policy and rerun the
   prod path from the stored release execution manifest; do not rebuild or
   bypass the approval gate.
