# Release Policy

Status: Active
Owner: nova release architecture
Last updated: 2026-03-28

## 1. Scope

This policy governs Nova package releases and release-adjacent validation.

Fixed constraints:

1. `main` is the only release branch.
2. Release plan/apply/publish/promote flows are manual GitHub workflow
   dispatches.
3. Prod package promotion consumes staged, gate-validated artifacts only.
4. Post-deploy route validation is optional and independent of package
   promotion.

## 1A. Authority / references

- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `docs/architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `docs/architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `docs/architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `docs/architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `docs/architecture/adr/ADR-0038-docs-authority-reset.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `docs/architecture/spec/SPEC-0027-public-api-v2.md`
- `docs/architecture/spec/SPEC-0028-export-workflow-state-machine.md`
- `docs/architecture/spec/SPEC-0029-platform-serverless.md`
- `docs/architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `docs/architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
- `docs/architecture/requirements.md`
- `docs/plan/GREENFIELD-WAVE-2-EXECUTION.md`

## 2. Security policy

1. GitHub workflows assume AWS roles using OIDC only.
2. Release signing material is read from AWS Secrets Manager at runtime only.
3. No long-lived AWS access keys are permitted in GitHub secrets.

## 3. Package policy

1. Selective per-unit versioning is required.
2. Python distributions publish via `twine --repository codeartifact`.
3. npm distributions publish via repo-scoped CodeArtifact npm config and
   `npm publish --no-progress`.
4. R releases publish tarball and detached signature assets as CodeArtifact
   generic packages.
5. Publish to `CODEARTIFACT_STAGING_REPOSITORY` only after manifest and gate
   validation pass.
6. Promote to `CODEARTIFACT_PROD_REPOSITORY` only from validated staged
   candidates.
7. Staging and prod repositories must differ.

## 4. Infrastructure policy

1. `infra/nova_cdk` is the only active repo-owned infrastructure surface.
2. Deleted repo-owned ECS/worker/runtime CloudFormation and pipeline-control
   plane paths are not part of release operations.

## 5. Required release evidence

Each release cycle must retain durable pointers for:

- release plan/apply/publish/promote workflow runs
- manifest SHA continuity
- post-deploy validation evidence when that workflow is used
- the PR or internal ticket that approved the release
