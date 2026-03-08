# Plan Index (Current State)

Status: Active planning index
Last updated: 2026-03-05

## Active authority set

- `docs/PRD.md`
- `docs/architecture/requirements.md`
- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/adr/ADR-0024-layered-architecture-authority-pack.md`
- `docs/architecture/adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md`
- `docs/architecture/adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md`
- `docs/architecture/adr/ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md`
- `docs/architecture/adr/ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md`
- `docs/architecture/adr/ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `docs/architecture/spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md`
- `docs/architecture/spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md`
- `docs/architecture/spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md`
- `docs/architecture/spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md`
- `docs/architecture/spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md`
- `docs/architecture/spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md`
- `docs/architecture/spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md`

## Adjacent deploy-governance authority

- `docs/architecture/adr/ADR-0030-native-cfn-modular-stack-architecture-for-nova-infrastructure-productization.md`
- `docs/architecture/adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md`
- `docs/architecture/adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md`
- `docs/architecture/spec/SPEC-0024-cloudformation-module-contract.md`
- `docs/architecture/spec/SPEC-0025-reusable-workflow-integration-contract.md`
- `docs/architecture/spec/SPEC-0026-ci-cd-iam-least-privilege-matrix.md`

## Active release execution artifacts

- `docs/plan/release/HARD-CUTOVER-CHECKLIST.md`
- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- `docs/plan/release/release-promotion-dev-to-prod-guide.md`
- `docs/plan/release/config-values-reference-guide.md`
- `docs/plan/release/RELEASE-RUNBOOK.md`
- `docs/plan/release/RELEASE-POLICY.md`

## Recent contract updates

- Active runtime authority IDs (`ADR-0024` through `ADR-0026`,
  `SPEC-0017` through `SPEC-0019`) were restored to runtime subjects.
- Distributed idempotency now has explicit runtime modes: local development may
  use `local_only`, while AWS-backed production requires
  `IDEMPOTENCY_MODE=shared_required` with `CACHE_REDIS_URL`; readiness treats
  the shared cache as critical only in that strict mode.
- Worker poison-message handling now leaves malformed SQS messages on the queue
  for retry/DLQ processing, while transient callback failures no longer delete
  the source message prematurely.
- Worker lane now executes canonical `transfer.process` jobs end-to-end, and
  the worker stack requires `JobsWorkerUpdateTokenSecretArn` plus queue-depth
  step scaling even when deployed for scale-from-zero.
- Worker callback retries now require durable `running` acceptance before copy
  execution and reuse a stable per-job export key so redelivery does not mint
  duplicate export artifacts.
- Release artifact downloaders now query GitHub Actions artifacts by name with
  `per_page=100` pagination fallback and fail fast on ambiguous live matches.
- Remote auth execution now reuses a lifespan-managed async HTTP client and the
  published Python packages ship `py.typed` markers as part of the supported
  type-safety contract.
- Auth0 reusable tenant workflow now requires successful contract validation
  before any import/export mutation step.
- Release IAM promotion controls now require explicit staged source and prod
  destination repository parameters for `CopyPackageVersions`.
- Nova owns complete public SDKs for Python, TypeScript, and R as the target
  client contract. Current Python SDK trees remain committed and drift-gated;
  TypeScript/R scaffolding remains in-repo as the completion path and must not
  be deleted.
- SDK-facing OpenAPI metadata now requires stable snake_case `operationId`
  values, semantic tags, and deterministic regeneration of committed Python
  SDK trees.
- Release planning/apply/gate automation now models both PyPI and npm workspace
  units; staged npm publication rewrites internal source dependencies to
  concrete semver, validates installability from CodeArtifact, and preserves
  the retained TypeScript helper contracts.

## Historical planning artifacts

- `docs/plan/HISTORY-INDEX.md`
- `docs/architecture/adr/superseded/`
- `docs/architecture/spec/superseded/`
- `docs/history/2026-03-v1-hard-cut/`
- `docs/history/2026-02-cutover/`
