# Release Runbook

Status: Active
Owner: nova release architecture
Last updated: 2026-03-29

## 1. Purpose

Execute the canonical Nova release flow: selective version planning, signed
release application, repo-owned runtime deployment via GitHub OIDC, staged
package publication, prod package promotion, and provenance-bound runtime
validation.

## 1A. Authority / references

- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/spec/superseded/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `docs/architecture/spec/SPEC-0027-public-api-v2.md`
- `docs/architecture/requirements.md`
- `docs/architecture/requirements-wave-2.md`
- `docs/plan/GREENFIELD-WAVE-2-EXECUTION.md`
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md` through `docs/architecture/adr/ADR-0038-docs-authority-reset.md`
- `docs/architecture/spec/SPEC-0027-public-api-v2.md` through `docs/architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`

## 2. Preconditions

1. `main` is green on the required hosted checks in
   `governance-lock-and-branch-protection.md`.
2. `RELEASE_AWS_ROLE_ARN`, `RUNTIME_DEPLOY_AWS_ROLE_ARN`, and
   `RELEASE_SIGNING_SECRET_ID` are configured in GitHub.
3. `AWS_REGION`, `CODEARTIFACT_DOMAIN`,
   `CODEARTIFACT_STAGING_REPOSITORY`,
   `CODEARTIFACT_PROD_REPOSITORY`,
   `RELEASE_ARTIFACT_BUCKET`,
   `RUNTIME_ENVIRONMENT`,
   `RUNTIME_API_DOMAIN_NAME`,
   `RUNTIME_CERTIFICATE_ARN`,
   `RUNTIME_HOSTED_ZONE_ID`,
   `RUNTIME_HOSTED_ZONE_NAME`,
   `RUNTIME_CFN_EXECUTION_ROLE_ARN`,
   `RUNTIME_JWT_ISSUER`,
   `RUNTIME_JWT_AUDIENCE`, and `RUNTIME_JWT_JWKS_URL` are configured in
   GitHub repository variables.
4. Staging and prod CodeArtifact repositories already exist and are distinct.
5. If the release includes npm packages, Node 24 LTS is available.
6. If the release includes R packages, runners provide the R toolchain needed
   for `R CMD build` and `R CMD check`.

## 3. GitHub release execution

### A. Plan

1. Trigger `Nova Release Plan` from `main`.
2. Confirm artifacts:
   - `changed-units.json`
   - `version-plan.json`

### B. Apply

1. Trigger `Nova Release Apply` from `main`.
2. Confirm the workflow:
   - checks out the selected `main` commit SHA
   - applies versions from the version plan
   - writes `docs/release/RELEASE-VERSION-MANIFEST.md`
   - creates a signed release commit locally from `main`
   - pushes the signed release commit to `main`
   - rebuilds the public API Lambda zip from that exact signed release commit
   - uploads the zip to `RELEASE_ARTIFACT_BUCKET`
   - writes `.artifacts/api-lambda-artifact.json`
   - uploads `release-apply-artifacts`.

### C. Signature gate

1. Confirm `Verify Release Signature` passes for the release automation
   commit.

### D. Deploy runtime

1. Trigger `Deploy Runtime` from `main`.
2. Supply:
   - `release_apply_run_id`
3. Confirm the workflow:
   - downloads immutable `release-apply-artifacts`
   - checks out the signed release commit from `release-apply-metadata.json`
   - assumes `RUNTIME_DEPLOY_AWS_ROLE_ARN` via GitHub OIDC
   - enables arm64 Docker asset builds on the runner via QEMU and Buildx
   - deploys `infra/nova_cdk` through `npx aws-cdk deploy`
   - uses `RUNTIME_CFN_EXECUTION_ROLE_ARN` for CloudFormation resource
     mutations and the CDK bootstrap publishing roles for container/file assets
   - creates or updates the Route 53 alias for the canonical API custom domain
   - writes `deploy-output.json` and `deploy-output.sha256`
   - uploads the `deploy-runtime-output` artifact
   - runs post-deploy validation against that deploy-output artifact
4. Confirm deploy-output authority succeeds:
   - `deploy-output.json` includes the release commit SHA, runtime version,
     `NovaPublicBaseUrl`, stack name, region, and stack outputs
   - `deploy-output.sha256` matches the canonical JSON payload
   - `post-deploy-validation-report.json` binds validation to the same
     deploy-output digest and runtime version

### E. Publish staged packages

1. Trigger `Publish Packages` from `main`.
2. Supply:
   - `release_apply_run_id`
   - `expected_manifest_sha256` when available
3. Confirm the workflow:
   - downloads immutable `release-apply-artifacts`
   - runs `scripts.release.codeartifact_gate`
   - publishes only to `CODEARTIFACT_STAGING_REPOSITORY`
   - smoke-tests staged npm packages when npm artifacts are present
4. Confirm gate validation succeeds:
   - `scripts.release.codeartifact_gate` verifies manifest SHA256, changed units, and version plan inputs
   - failures raise `GateError` and fail the job non-zero
   - successful runs produce `codeartifact-gate-report.json` and `codeartifact-promotion-candidates.json`

### F. Promote staged packages to prod

1. Trigger `Promote Prod` from `main`.
2. Supply:
   - `manifest_sha256`
   - `changed_units_json` or `changed_units_path`
   - `changed_units_sha256`
   - `version_plan_json` or `version_plan_path`
   - `version_plan_sha256`
   - `promotion_candidates_json` or `promotion_candidates_path`
   - `promotion_candidates_sha256`
3. Confirm the workflow validates input digests and copies staged package
   versions from `CODEARTIFACT_STAGING_REPOSITORY` to
   `CODEARTIFACT_PROD_REPOSITORY`.
4. Confirm promotion validation succeeds:
   - the workflow re-runs `scripts.release.codeartifact_gate` to verify digest integrity
   - digest mismatches fail with a `sha256 mismatch` error
   - successful runs produce `validated-promotion-candidates.json`

### G. Re-run post-deploy runtime validation when needed

1. Trigger `Post Deploy Validate` when you need to revalidate an existing
   deploy-output artifact.
2. Supply:
   - `deploy_run_id`
   - `deploy_artifact_name` when the artifact name is not
     `deploy-runtime-output`
3. Confirm `validation_status=passed` and retain the uploaded
   `post-deploy-validation-report` artifact.
4. Before attempting remote cleanup or validation troubleshooting, verify that
   the target account actually contains a deployed Nova runtime. Accounts with
   only release-artifact buckets, CDK bootstrap resources, or other supporting
   infrastructure do not have a live Nova runtime to inspect.

## 4. Evidence capture

Capture durable pointers for:

1. `Nova Release Plan` workflow run
2. `Nova Release Apply` workflow run
3. `Verify Release Signature` workflow run
4. `Deploy Runtime` workflow run
5. `Publish Packages` workflow run
6. `Promote Prod` workflow run
7. `Post Deploy Validate` workflow run when used
8. `RELEASE-VERSION-MANIFEST.md` SHA continuity through publish and promotion
9. Gate validation artifacts:
   - `codeartifact-gate-report.json`
   - `codeartifact-promotion-candidates.json`
10. API deploy artifact evidence:
   - `api-lambda-artifact.json`
   - `release-apply-metadata.json`
   - S3 key under
     `runtime/nova-file-api/<release_commit_sha>/<artifact_sha256>/nova-file-api-lambda.zip`
11. Runtime deploy authority evidence:
   - `deploy-output.json`
   - `deploy-output.sha256`
   - `post-deploy-validation-report.json`

## 5. Rollback guidance

1. If staged publish fails, fix forward from `main` and rerun the failed step.
2. If prod promotion fails, fix the staged payload or repository permissions
   and rerun `Promote Prod`; do not bypass the input-digest gates.
3. If runtime deploy fails, fix forward from `main`, rerun `Deploy Runtime`,
   and treat the newest successful `deploy-runtime-output` artifact as the
   only active validation target.
