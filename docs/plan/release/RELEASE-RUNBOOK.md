# Release Runbook

Status: Active
Owner: nova release architecture
Last updated: 2026-03-05

## 1. Purpose

Execute release flow for selective versioning, signed commit generation, and
Dev to Prod AWS promotion.

## 1A. Modular guide set

Use the modular operator guide set for provisioning and setup details:

- `../../runbooks/README.md`
- `deploy-runtime-cloudformation-environments-guide.md`
- `day-0-operator-checklist.md`
- `scripts/release/day-0-operator-command-pack.sh`
- `aws-oidc-and-iam-role-setup-guide.md`
- `aws-secrets-provisioning-guide.md`
- `config-values-reference-guide.md`
- `github-actions-secrets-and-vars-setup-guide.md`
- `codeconnections-activation-and-validation-guide.md`
- `deploy-nova-cicd-end-to-end-guide.md`
- `release-promotion-dev-to-prod-guide.md`
- `troubleshooting-and-break-glass-guide.md`
- `BROWSER-LIVE-VALIDATION-CHECKLIST.md`

## 2. Preconditions

1. `main` is green on CI (`ci.yml`).
2. Release OIDC role and signing secret are provisioned.
3. CodeConnections source connection is `AVAILABLE`.
4. Runtime stacks are deployed for `dev` and `prod`, and validation base URLs
   are captured from canonical SSM base-url markers for both services:
   `/nova/dev/nova-file-api/base-url`, `/nova/prod/nova-file-api/base-url`,
   `/nova/dev/nova-auth-api/base-url`, and `/nova/prod/nova-auth-api/base-url`.
5. Runtime service stacks are configured for ECS-native blue/green with:
   - `EcsInfrastructureRoleArn`
   - `DeploymentRollbackAlarmNamePrimary`
   - `DeploymentRollbackAlarmNameSecondary`
6. Public ALB deployments expose `PublicAlbWebAclArn` from the runtime cluster
   stack.
7. Dev and Prod digest-marker deployment stack parameters are configured for
   both file and auth services.
8. Release build project parameters provide CodeArtifact and ECR targets:
   - `CODEARTIFACT_DOMAIN`
   - `CODEARTIFACT_STAGING_REPOSITORY`
   - `CODEARTIFACT_PROD_REPOSITORY`
   - `ECR_REPOSITORY_URI` (or `ECR_REPOSITORY_NAME`)
9. IAM roles stack is deployed with promotion repository parameters:
   - `CodeArtifactPromotionSourceRepositoryName`
   - `CodeArtifactPromotionDestinationRepositoryName`

## 3. GitHub release execution

### A. Plan

1. Trigger `Nova Release Plan` (`release-plan.yml`) or wait for a `main` push
   run.
2. Confirm artifacts:
   - `changed-units.json`
   - `version-plan.json`

### B. Apply

1. Trigger `Nova Release Apply` (`release-apply.yml`, displayed as `Nova
   Release Apply` in Actions; older docs and CLI snippets may still show
   `Apply Release Plan`).
2. Confirm workflow:
   - runs from `main` only (manual dispatch on non-main refs is blocked)
   - for `workflow_run`, checks out `workflow_run.head_sha`
   - applies versions from version plan
   - writes release manifest
   - creates signed commit on `main`

### C. Signature gate

1. Confirm `Verify Release Signature` passes.
2. For release automation commits, `verified=true` is required.

### D. Package staged publish gate

1. Trigger `Publish Packages` (or wait for `Nova Release Apply` completion trigger).
2. Confirm `scripts.release.codeartifact_gate` generated:
   - `.artifacts/codeartifact-gate-report.json`
   - `.artifacts/codeartifact-promotion-candidates.json`
3. Confirm package uploads target `CODEARTIFACT_STAGING_REPOSITORY` only.
4. Confirm promotion copies from `CODEARTIFACT_STAGING_REPOSITORY` to
   `CODEARTIFACT_PROD_REPOSITORY`.

### E. Post-deploy route validation gate

1. Trigger `Post Deploy Validate` (`post-deploy-validate.yml`) after deployment.
2. Supply `validation_base_url` and `auth_validation_base_url` using deployed
   HTTPS endpoints.
3. Confirm wrapper calls reusable API:
   - `.github/workflows/reusable-post-deploy-validate.yml`
4. Confirm artifact upload:
   - `post-deploy-validation-report`
   - report file: `post-deploy-validation-report.json`
5. Confirm reusable workflow output:
   - `validation_status=passed`
6. Confirm report contains both `file_target` and `auth_target` route evidence.

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
   - `manifest_sha256` equal to `RELEASE_MANIFEST_SHA256`
     (`SHA256(docs/plan/release/RELEASE-VERSION-MANIFEST.md)`); a gate report
     may carry the value, but the manifest is the authority
   - `changed_units_json` from staged gate artifact (`changed-units.json`)
   - `version_plan_json` from staged gate artifact (`version-plan.json`)
   - `promotion_candidates_json` from `codeartifact-promotion-candidates.json`
4. Confirm package promotion uses `aws codeartifact copy-package-versions` from
   `CODEARTIFACT_STAGING_REPOSITORY` to `CODEARTIFACT_PROD_REPOSITORY`.
5. Manual approval must include reviewer identity and timestamp.
6. Confirm immutable artifact continuity:
   - Prod promotion uses the same `FILE_IMAGE_DIGEST` exported from Build/Dev.
   - Prod promotion uses the same `AUTH_IMAGE_DIGEST` exported from Build/Dev.
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
8. Explicit digest continuity evidence (Dev -> Prod file/auth digest match).
9. Post-deploy route validation artifact link and status output for both
   services.
10. Link entry in `docs/plan/release/evidence-log.md`.
11. Runtime WAF evidence for any internet-facing ALB (`PublicAlbWebAclArn` or
    equivalent stack output).
12. Immutable release-plan artifact continuity evidence:
    `changed-units.json` and `version-plan.json` consumed by release-apply and
    publish-packages from upstream workflow artifacts, not recomputed locally.
