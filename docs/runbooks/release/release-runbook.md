# Release Runbook

Status: Active
Owner: nova release architecture
Last updated: 2026-03-28

## 1. Purpose

Execute the canonical Nova package-release flow: selective version planning,
signed release application, staged package publication, prod package
promotion, and optional post-deploy route validation.

## 2. Preconditions

1. `main` is green on the required hosted checks in
   `governance-lock-and-branch-protection.md`.
2. `RELEASE_AWS_ROLE_ARN` and `RELEASE_SIGNING_SECRET_ID` are configured in
   GitHub.
3. `AWS_REGION`, `CODEARTIFACT_DOMAIN`,
   `CODEARTIFACT_STAGING_REPOSITORY`, and
   `CODEARTIFACT_PROD_REPOSITORY` are configured in GitHub repository
   variables.
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
   - creates a signed release commit on `main`

### C. Signature gate

1. Confirm `Verify Release Signature` passes for the release automation
   commit.

### D. Publish staged packages

1. Trigger `Publish Packages` from `main`.
2. Supply:
   - `release_apply_run_id`
   - `expected_manifest_sha256` when available
3. Confirm the workflow:
   - downloads immutable `release-apply-artifacts`
   - runs `scripts.release.codeartifact_gate`
   - publishes only to `CODEARTIFACT_STAGING_REPOSITORY`
   - smoke-tests staged npm packages when npm artifacts are present

### E. Promote staged packages to prod

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

### F. Optional post-deploy route validation

1. Trigger `Post Deploy Validate` after a manual or external deployment.
2. Supply the deployed HTTPS base URL.
3. Confirm `validation_status=passed` and retain the uploaded
   `post-deploy-validation-report` artifact.

## 4. Evidence capture

Capture durable pointers for:

1. `Nova Release Plan` workflow run
2. `Nova Release Apply` workflow run
3. `Verify Release Signature` workflow run
4. `Publish Packages` workflow run
5. `Promote Prod` workflow run
6. `Post Deploy Validate` workflow run when used
7. `RELEASE-VERSION-MANIFEST.md` SHA continuity through publish and promotion

## 5. Rollback guidance

1. If staged publish fails, fix forward from `main` and rerun the failed step.
2. If prod promotion fails, fix the staged payload or repository permissions
   and rerun `Promote Prod`; do not bypass the input-digest gates.
