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
