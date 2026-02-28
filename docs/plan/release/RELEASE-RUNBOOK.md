# Release Runbook

Status: Active
Owner: nova release architecture
Last updated: 2026-02-24

## 1. Purpose

Execute release flow for selective versioning, signed commit generation, and
Dev to Prod AWS promotion.

## 1A. Modular guide set

Use the modular operator guide set for provisioning and setup details:

- `documentation-index.md`
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

## 2. Preconditions

1. `main` is green on CI (`ci.yml`).
2. Release OIDC role and signing secret are provisioned.
3. CodeConnections source connection is `AVAILABLE`.
4. Dev and Prod deployment stack parameters are configured.
5. Release build project parameters provide CodeArtifact and ECR targets:
   - `CODEARTIFACT_DOMAIN`
   - `CODEARTIFACT_REPOSITORY`
   - `ECR_REPOSITORY_URI` (or `ECR_REPOSITORY_NAME`)

## 3. GitHub release execution

### A. Plan

1. Trigger `Nova Release Plan` (or wait for `main` push run).
2. Confirm artifacts:
   - `changed-units.json`
   - `version-plan.json`

### B. Apply

1. Trigger `Nova Release Apply`.
2. Confirm workflow:
   - runs from `main` only (manual dispatch on non-main refs is blocked)
   - for `workflow_run`, checks out `workflow_run.head_sha`
   - applies versions from version plan
   - writes release manifest
   - creates signed commit on `main`

### C. Signature gate

1. Confirm `Verify Release Signature` passes.
2. For release automation commits, `verified=true` is required.

## 4. AWS promotion execution

1. Confirm CodePipeline source event ingests signed release commit.
2. Confirm stages in order:
   - Build
   - DeployDev
   - ValidateDev
   - ManualApproval
   - DeployProd
   - ValidateProd
3. Confirm release build uploads changed packages to CodeArtifact via
   `twine --repository codeartifact`.
4. Manual approval must include reviewer identity and timestamp.
5. Confirm immutable artifact continuity:
   - Prod promotion uses the same `IMAGE_DIGEST` exported from Build/Dev.
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
   - `IMAGE_DIGEST`
   - `PUBLISHED_PACKAGES`
   - `RELEASE_MANIFEST_SHA256`
8. Explicit digest continuity evidence (Dev -> Prod `IMAGE_DIGEST` match).
