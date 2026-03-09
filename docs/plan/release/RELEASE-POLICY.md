# Release Policy

Status: Active
Owner: nova release architecture
Last updated: 2026-03-05

## 1. Scope

This policy governs runtime releases for `nova` with these fixed constraints:

1. Environments are exactly `dev` and `prod`.
2. Runtime topology remains ECS/Fargate + SQS worker.
3. No Lambda-based runtime orchestration is introduced in this scope.

Companion modular setup guides:

- `../../runbooks/README.md`
- `aws-secrets-provisioning-guide.md`
- `aws-oidc-and-iam-role-setup-guide.md`

## 2. Branch and artifact policy

1. `main` is the only release branch.
2. Release planning and release apply automation run from `main`.
3. `release-apply` manual dispatch runs are allowed only on `main`.
4. `release-apply` workflow-run executions are allowed only for successful
   `main`-branch plan runs and must checkout `workflow_run.head_sha`.
5. Release commits from automation must be cryptographically signed.
6. AWS promotion consumes immutable artifacts from signed source state.

## 3. Promotion policy

1. Dev deployment and validation must succeed first.
2. Manual approval is mandatory before Prod deployment.
3. Prod uses exactly the same immutable artifact identifiers promoted from Dev.
4. Rebuilds between Dev and Prod are prohibited.

## 4. Security policy

1. GitHub workflows assume AWS roles using OIDC only.
2. OIDC trust policy constraints must include `aud=sts.amazonaws.com` and
   scoped `sub` claim patterns.
3. No long-lived AWS access keys are permitted in GitHub secrets.
4. Release signing material is read from AWS Secrets Manager at runtime only.

## 5. Package policy

1. Selective per-unit versioning is required.
2. Release build uploads must target CodeArtifact via:
   - `twine --repository codeartifact` for Python distributions
   - `npm publish` against the staged npm endpoint for release-prepared npm
     artifacts
3. Selective publish package paths are resolved from signed release commit diff
   (`HEAD^..HEAD`) to avoid empty publish sets on manifest-touching release
   commits.
4. Internal package namespace controls are enforced with CodeArtifact package
   group origin controls.
5. Internal package groups must block external upstream ingestion.
6. Publish to staged channel (`CODEARTIFACT_STAGING_REPOSITORY`) only after manifest, version, and namespace gates pass.
7. Promotion to prod channel must consume only staged and gate-validated versions via `copy-package-versions`.
8. Source npm manifests may use repo-local dependency specifiers (for example
   `file:../nova_sdk_fetch`) for local development, but staged publish
   artifacts must rewrite internal npm dependencies to concrete semver versions
   and remove publish-blocking `private: true`.
9. Staged npm validation must install from CodeArtifact with `npm install --no-progress`
   and verify the generated/private TypeScript SDK subpath contracts before
   prod promotion.
10. Internal npm package-group policy for `/npm/${CodeArtifactInternalNpmScope}/*` must allow direct
   publish while blocking both external and internal upstream ingestion.
11. Promotion must include and verify `RELEASE_MANIFEST_SHA256`, where the value
   is the actual SHA256 of `docs/plan/release/RELEASE-VERSION-MANIFEST.md`.
12. Public Python SDK releases must classify OpenAPI tag or `operationId`
   renames as MAJOR changes because they rename generated endpoint modules or
   functions.

## 5A. Runtime deployment policy

1. Runtime API service deployment uses ECS-native blue/green controls on
   `AWS::ECS::Service` resources with:
   - `DeploymentController.Type=ECS`
   - `DeploymentConfiguration.Strategy=BLUE_GREEN`
2. Queue worker services remain ECS rolling deployments with deployment circuit
   breaker protection; they do not use load-balancer traffic shifting.
3. Public ALB WebACL/WAF association is environment-template specific and must
   be validated against the deployed runtime stack definitions for each lane.

## 6. Required release evidence

Each release cycle must retain evidence in:

- `docs/plan/release/RELEASE-VERSION-MANIFEST.md`
- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- `docs/plan/release/evidence-log.md`
- `docs/plan/release/RELEASE-RUNBOOK.md` execution notes
