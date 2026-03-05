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

## Active release execution artifacts

- `docs/plan/release/HARD-CUTOVER-CHECKLIST.md`
- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- `docs/plan/release/release-promotion-dev-to-prod-guide.md`
- `docs/plan/release/config-values-reference-guide.md`
- `docs/plan/release/RELEASE-RUNBOOK.md`
- `docs/plan/release/RELEASE-POLICY.md`

## Recent contract updates

- Auth0 reusable tenant workflow now requires successful contract validation
  before any import/export mutation step.
- Release IAM promotion controls now require explicit staged source and prod
  destination repository parameters for `CopyPackageVersions`.

## Historical planning artifacts

- `docs/plan/HISTORY-INDEX.md`
- `docs/history/2026-03-v1-hard-cut/`
- `docs/history/2026-02-cutover/`
