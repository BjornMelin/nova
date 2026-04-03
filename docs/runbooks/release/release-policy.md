# Release Policy

Status: Active
Owner: nova release architecture
Last updated: 2026-04-02

## 1. Scope

This policy governs Nova package releases and release-adjacent validation.

Fixed constraints:

1. `main` is the only release branch.
2. Release prep is human-authored and merged through the protected `main`
   branch as a normal PR.
3. Post-merge publish, promotion, and runtime deployment run through the AWS
   release control plane only.
4. Prod package promotion consumes staged, gate-validated artifacts only.
5. Post-deploy runtime validation is optional and independent of package
   promotion.

## 1A. Authority / references

- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `docs/architecture/adr/ADR-0038-docs-authority-reset.md`
- `docs/architecture/spec/SPEC-0004-ci-cd-and-docs.md`
- `docs/architecture/spec/SPEC-0029-platform-serverless.md`
- `docs/contracts/deploy-output-authority-v2.schema.json`
- `docs/contracts/release-prep-v1.schema.json`
- `docs/contracts/release-execution-manifest-v1.schema.json`
- `release/README.md`

## 2. Security policy

1. GitHub workflows do not execute Nova release, promotion, or runtime deploy
   actions against AWS.
2. AWS CodeBuild projects fetch release signing material from AWS Secrets
   Manager at runtime only.
3. Non-secret runtime deploy configuration is read from SSM Parameter Store
   JSON documents, not duplicated across GitHub repository variables.
4. No long-lived AWS access keys are permitted in GitHub secrets.

## 3. Package policy

1. Selective per-unit versioning is required.
2. The committed release intent is `release/RELEASE-PREP.json`.
3. The human-reviewable release mirror is
   `release/RELEASE-VERSION-MANIFEST.md`.
4. Python distributions publish via `twine --repository codeartifact`.
5. npm distributions publish via repo-scoped CodeArtifact npm config and
   `npm publish --no-progress`.
6. R releases publish tarball and detached signature assets as CodeArtifact
   generic packages.
7. Publish to `CODEARTIFACT_STAGING_REPOSITORY` only after manifest and gate
   validation pass.
8. Promote to `CODEARTIFACT_PROD_REPOSITORY` only from validated staged
   candidates.
9. Staging and prod repositories must differ.

## 4. Infrastructure policy

1. `infra/nova_cdk` is the only active repo-owned infrastructure surface.
2. Deleted GitHub publish/deploy/promote workflows are not active release
   executors.
3. The active release control plane is provisioned from `infra/nova_cdk`.

## 5. Required release evidence

Each release cycle must retain durable pointers for:

- release-plan workflow runs and the release PR that carried the committed prep artifacts
- CodePipeline / CodeBuild execution ids for staging and prod
- manifest SHA continuity
- post-deploy runtime validation evidence when that workflow is used
- the PR or internal ticket that approved the release
