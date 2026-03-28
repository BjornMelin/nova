---
ADR: 0024
Title: Layered runtime authority pack for the Nova monorepo
Status: Accepted
Version: 2.0
Date: 2026-03-05
Related:
  - "[AGENTS.md runtime authority](../../../AGENTS.md)"
  - "[README.md runtime authority summary](../../../README.md)"
  - "[PRD authority baseline](../../PRD.md)"
  - "[Architecture requirements baseline](../requirements.md)"
  - "[Plan index authority set](../../plan/PLAN.md)"
  - "[Runbooks authority index](../../runbooks/README.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[ADR-0025: Runtime monorepo component boundaries and ownership](./ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md)"
  - "[ADR-0026: Fail-fast runtime configuration and safe auth execution](./ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)"
  - "[ADR-0027: Hard-cut downstream integration and consumer contract enforcement](./ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md)"
  - "[ADR-0028: Auth0 tenant ops reusable workflow API contract](./ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md)"
  - "[ADR-0029: SSM runtime base URL authority for deploy validation](./ADR-0029-ssm-runtime-base-url-authority-for-deploy-validation.md)"
  - "[SPEC-0000: HTTP API Contract](../spec/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](../spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0017: Runtime component topology and ownership contract](../spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md)"
  - "[SPEC-0018: Runtime configuration and startup validation contract](../spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[SPEC-0019: Auth execution and threadpool safety contract](../spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md)"
  - "[SPEC-0031: Docs and tests authority reset](../spec/SPEC-0031-docs-and-tests-authority-reset.md)"
  - "[SPEC-0021: Downstream hard-cut integration and consumer validation contract](../spec/SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md)"
  - "[SPEC-0022: Auth0 tenant ops reusable workflow contract](../spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md)"
  - "[SPEC-0023: SSM runtime base-url contract for deploy validation](../spec/SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md)"
---

## Summary

Nova keeps one active runtime authority pack. Runtime API authority,
package-boundary ownership, runtime configuration/auth safety, and downstream
integration validation must be documented under truthful identifiers and remain
synchronized across AGENTS, README, PRD, requirements, plan, runbooks, and
architecture indexes.

## Context

Nova is greenfield and hard-cut by default. We do not preserve parallel
authority chains, stale paths, or misleading labels that imply a different
subject than the file actually governs.

Runtime authority needs a stable layered structure:

- route and HTTP contract authority
- runtime component topology and startup/auth safety authority
- downstream integration and validation authority

Adjacent deploy-governance docs remain canonical, but they are not part of the
active runtime authority pack.

## Alternatives and scored decision

### Criteria and weights

- Solution leverage: 35%
- Application value: 30%
- Maintenance and cognitive load: 25%
- Architectural adaptability: 10%

### Option scores

| Option | Weighted score (/10) |
| --- | ---: |
| A. Keep stale labels and mixed subject ownership across active docs | 3.9 |
| B. Restore one truthful layered runtime authority pack and isolate deploy-governance under separate identifiers | **9.8** |
| C. Add overlay docs while leaving current identifier drift in place | 5.4 |

Threshold policy: only options `>= 9.0` are accepted.

## Decision

Choose **Option B**.

### Required characteristics

1. Active runtime authority includes:
   - `docs/PRD.md`
   - `docs/architecture/requirements.md`
   - `ADR-0023` through `ADR-0029`
   - `SPEC-0000`
   - `SPEC-0015` through `SPEC-0023`
   - `docs/plan/PLAN.md`
   - `docs/runbooks/README.md`
2. Runtime package boundary, startup validation, and auth-execution rules are
   owned by `ADR-0025`, `ADR-0026`, `SPEC-0017`, `SPEC-0018`, and `SPEC-0019`.
3. Downstream validation and reusable consumer contracts remain in
   `ADR-0027` through `ADR-0029` and `SPEC-0021` through `SPEC-0023`.
4. Adjacent deploy-governance authority is limited to `ADR-0030` through
   `ADR-0032` and `SPEC-0024` through `SPEC-0026`.
5. README, AGENTS, PRD, requirements, plan, runbooks, standards docs, and
   indexes must all reference the same active runtime authority pack in the
   same change.

## Consequences

### Positive

- Engineers can trust the active authority graph again.
- Runtime safety and component ownership stay close to the code they govern.
- Deploy-governance docs remain available without polluting runtime authority.
- Review and test guardrails can key off one truthful active documentation set.

### Trade-offs

- Existing cross-links and indexes require a one-time cleanup pass.
- Historical references that used displaced identifiers must be updated or
  archived.

## Explicit non-decisions

- No duplicate active runtime authority list.
- No stale link preservation inside active docs.
- No compatibility note that treats broken or misleading active paths as still
  valid.

## Changelog

- 2026-03-05: Restored `ADR-0024` as the layered runtime authority-pack
  decision and moved deploy-governance topics to `ADR-0030` through `ADR-0032`.
