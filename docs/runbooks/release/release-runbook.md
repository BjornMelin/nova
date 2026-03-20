# Release Runbook

Status: Active
Owner: nova release architecture
Last updated: 2026-03-18

## 1. Purpose

Execute release flow for selective versioning, signed commit generation, and
Dev to Prod AWS promotion.

Canonical documentation authority chain:
[README.md#canonical-documentation-authority-chain](README.md#canonical-documentation-authority-chain).

## 1A. Modular guide set

Provisioning, validation, and setup guides are indexed in
[README.md](README.md) (this directory) and
[`../README.md`](../README.md). Use
`scripts/release/day-0-operator-command-pack.sh` with the day-0 checklist.

## 2. Preconditions

1. `main` is green on CI (`ci.yml`).
2. Release OIDC role and signing secret are provisioned.
3. CodeConnections source connection is `AVAILABLE`.
4. Runtime stacks are deployed for `dev` and `prod`, and validation base URLs
   are captured from canonical base-url marker stacks:
   `${PROJECT}-ci-dev-service-base-url` and
   `${PROJECT}-ci-prod-service-base-url`.
5. Dev and Prod digest-marker deployment stack parameters are configured.
6. Release build project parameters provide CodeArtifact and ECR targets:
   - `CODEARTIFACT_DOMAIN`
   - `CODEARTIFACT_STAGING_REPOSITORY`
   - `CODEARTIFACT_PROD_REPOSITORY`
   - `ECR_REPOSITORY_URI` (or `ECR_REPOSITORY_NAME`)
7. Release runners provide the R toolchain needed for `R CMD build` and
   `R CMD check` on the package release line, and the shared conformance
   helper (`scripts/checks/verify_r_cmd_check.sh`) fails the R lane if
   `R CMD check` reports warnings, while running `R CMD check --no-manual`
   so runners do not require `pdflatex`.
8. Release-image build environments provide Docker BuildKit plus the `buildx`
   CLI plugin.
9. IAM roles stack is deployed with promotion repository parameters:
   - `CodeArtifactPromotionSourceRepositoryName`
   - `CodeArtifactPromotionDestinationRepositoryName`

## 3. GitHub release execution

### A. Plan

1. Trigger `Nova Release Plan` (`release-plan.yml`) from `main`.
2. Confirm artifacts:
   - `changed-units.json`
   - `version-plan.json`

### B. Apply

1. Trigger `Nova Release Apply` (`release-apply.yml`, displayed as `Nova
   Release Apply` in Actions; older docs and CLI snippets may still show
   `Apply Release Plan`).
2. Confirm workflow:
   - runs from `main` only (manual dispatch on non-main refs is skipped by the branch guard)
   - checks out the selected `main` commit SHA for the manual dispatch run
   - applies versions from version plan
   - writes release manifest
   - creates signed commit on `main`

### C. Signature gate

1. Confirm `Verify Release Signature` passes.
2. For release automation commits, `verified=true` is required.

### D. Package staged publish gate

1. Trigger `Publish Packages` manually from `main` with the successful
   `Nova Release Apply` run id.
2. Confirm `scripts.release.codeartifact_gate` generated:
   - `.artifacts/r-publish-report.json`
   - `.artifacts/codeartifact-gate-report.json`
   - `.artifacts/codeartifact-promotion-candidates.json`
   - `.artifacts/npm-publish-report.json` when npm packages participate
3. Confirm Python package uploads use `twine`, TypeScript package uploads use
   `aws codeartifact login --tool npm` plus `npm publish --no-progress`, and
   R package releases use `R CMD build` and `R CMD check` before tarball
   evidence is stored. The R publish flow writes `.artifacts/r-publish-report.json`,
   uploads the tarball and detached `.sig` as separate CodeArtifact generic
   assets, publishes the tarball `--unfinished`, and rewrites the report with
   `published_assets` after upload. The shared conformance helper
   (`scripts/checks/verify_r_cmd_check.sh`) fails the R lane if `R CMD check`
   reports warnings, while using `R CMD check --no-manual` so the lane does
   not depend on `pdflatex`.
   When the runner uses npm 10.x, AWS CLI v2.9.5 or newer is required.
4. Confirm staged npm smoke installs succeed from
   `CODEARTIFACT_STAGING_REPOSITORY` before prod promotion and validate the
   release-grade TypeScript subpath contracts.
5. Confirm package uploads target `CODEARTIFACT_STAGING_REPOSITORY` only and
   that R generic package tarball and signature assets are captured as signed
   release evidence.
6. Confirm promotion copies from `CODEARTIFACT_STAGING_REPOSITORY` to
   `CODEARTIFACT_PROD_REPOSITORY`.

### E. Post-deploy route validation gate

1. Trigger `Post Deploy Validate` (`post-deploy-validate.yml`) after deployment.
2. Supply `validation_base_url` from the canonical marker-derived base URL:
   `${PROJECT}-ci-<env>-service-base-url`, or read the matching
   `/nova/{env}/{service}/base-url` SSM parameter that the marker stack manages.
3. Confirm wrapper calls reusable API:
   - `post-deploy-validate.yml` calls reusable workflow `.github/workflows/reusable-post-deploy-validate.yml`.
4. Confirm artifact upload:
   - `post-deploy-validation-report`
   - report file: `post-deploy-validation-report.json`
5. Confirm post-deploy validation result via the caller workflow run context, because the reusable workflow executes through `workflow_call` and appears inside the caller run:
   - In workflow run page, verify `post-deploy-validate` job status is `success` (or failure as evidence).
   - In the same caller run, inspect logs and artifacts for both `post-deploy-validate.yml` (wrapper) and `.github/workflows/reusable-post-deploy-validate.yml`; confirm completion and result details there.
6. Confirm `post-deploy-validation-report` artifact content:
   - Artifact exists and contains a report payload (typically `post-deploy-validation-report.json`).
   - Report status reflects the pass result in payload fields (for example `validation_status=passed` when present in logs).
7. If the artifact is missing or ambiguous, search workflow logs for explicit completion markers (for example `validation_status=passed` or equivalent) from the reusable workflow run.

## 4. AWS promotion execution

1. Confirm CodePipeline source event ingests signed release commit.
2. Confirm stages in order:
   - Source
   - Build
   - DeployDev
   - ValidateDev
   - ManualApproval
   - DeployProd
   - ValidateProd
3. Run `Promote Prod` workflow with:
   - `manifest_sha256` from `codeartifact-gate-report.json`
   - `changed_units_json` from staged gate artifact (`changed-units.json`)
   - `version_plan_json` from staged gate artifact (`version-plan.json`)
   - `promotion_candidates_json` from `codeartifact-promotion-candidates.json`
4. Confirm package promotion uses `aws codeartifact copy-package-versions` from
   `CODEARTIFACT_STAGING_REPOSITORY` to `CODEARTIFACT_PROD_REPOSITORY`.
   Scoped npm packages must provide `--namespace` and the unscoped package
   component when copied.
5. Manual approval must include reviewer identity and timestamp.
6. Confirm immutable artifact continuity:
   - Prod promotion uses the same `FILE_IMAGE_DIGEST` and
     `AUTH_IMAGE_DIGEST` exported from Build/Dev.
   - No rebuild occurs between Dev and Prod stages.

## 5. Rollback guidance

1. If Dev deploy fails, stop promotion and fix forward from `main`.
2. If Prod deploy fails, use previous known-good immutable artifact and
   redeploy via CloudFormation stack update.
3. Record rollback event and cause in release notes/runbook evidence.

## 6. Evidence capture

For each run capture:

1. Release plan workflow run URL.
2. Release apply workflow run URL.
3. Signature verification workflow run URL.
4. CodePipeline execution ID and stage outcomes.
5. Manual approval actor and timestamp.
6. Dev and Prod validation evidence links.
7. Build exported variables:
   - `FILE_IMAGE_DIGEST`
   - `AUTH_IMAGE_DIGEST`
   - `PUBLISHED_PACKAGES`
   - `RELEASE_MANIFEST_SHA256`
8. Explicit digest continuity evidence (Dev -> Prod `FILE_IMAGE_DIGEST` and
   `AUTH_IMAGE_DIGEST` match).
9. Post-deploy route validation artifact link and workflow/job status or log markers.
10. Consolidate the above into a durable promotion record (for example release PR
    description, internal change ticket, or org-owned artifact store URI); avoid
    duplicating the same pointers in `docs/` unless policy explicitly requires
    it--see `release-policy.md` §6.
11. Runtime WAF evidence for any internet-facing ALB (`PublicAlbWebAclArn` or
    equivalent stack output).
12. Immutable release-plan artifact continuity evidence:
    `changed-units.json` and `version-plan.json` consumed by release-apply and
    publish-packages from upstream workflow artifacts, not recomputed locally.
13. For TypeScript releases, retain the staged npm smoke output proving
    installability, curated export shape, and subpath/client compatibility from
    CodeArtifact.
14. For R releases, retain the tarball path, signature path, both SHA256
    values, build/check logs, `.artifacts/r-publish-report.json`, and
    CodeArtifact generic package evidence.
15. Record the explicit `release_apply_run_id` used for staged publish.

## 7. Local npm operator rule

For local developer shells, keep CodeArtifact npm configuration repo-scoped:

```bash
cd <NOVA_REPO_ROOT>
eval "$(npm run -s codeartifact:npm:env)"
```

Use the committed `.npmrc` plus the generated repo-local
`.npmrc.codeartifact`. Stop here if the goal is only to configure
CodeArtifact authentication for the current shell.

If you need to install workspace dependencies locally, run:

```bash
npm ci
```

If you only want to validate registry/auth behavior without modifying the repo
working tree, run the install in a temporary directory instead of the repo
root.
If you need a different account/domain/repository, set `AWS_REGION`,
`CODEARTIFACT_DOMAIN`, and/or `CODEARTIFACT_STAGING_REPOSITORY` before running
the helper. Do not run `aws codeartifact login --tool npm` on a workstation
unless you explicitly intend to rewrite global `~/.npmrc`. CI may still use
`aws codeartifact login --tool npm` because runners are ephemeral. When the
runner uses npm 10.x, AWS CLI v2.9.5 or newer is required.

## 8. Local Docker operator rule

For local service-image verification, operators must use a Docker CLI with
BuildKit and `buildx` available. Use
[`docker-buildx-credential-helper-setup.md`](../provisioning/docker-buildx-credential-helper-setup.md) when the workstation hits
credential-helper or plugin-path failures before the repo Dockerfiles build.
