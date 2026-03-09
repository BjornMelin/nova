---
ADR: 0025
Title: Runtime monorepo component boundaries and ownership
Status: Accepted
Version: 2.0
Date: 2026-03-05
Related:
  - "[ADR-0024: Layered runtime authority pack for the Nova monorepo](./ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0026: Fail-fast runtime configuration and safe auth execution](./ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)"
  - "[SPEC-0017: Runtime component topology and ownership contract](../spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md)"
  - "[SPEC-0018: Runtime configuration and startup validation contract](../spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[SPEC-0019: Auth execution and threadpool safety contract](../spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](./ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
---

## Summary

Nova runtime ownership is package-first. App directories are thin ASGI wrappers;
runtime packages own request handling, orchestration, auth, and worker logic;
the Dash bridge is an adapter over canonical Nova contracts instead of a second
runtime authority.

## Context

The runtime now lives in one monorepo, but the architecture only stays legible
if package ownership remains explicit:

- `apps/nova_file_api_service/` and `apps/nova_auth_api_service/` boot services.
- `packages/nova_file_api/` owns transfer and job control-plane behavior.
- `packages/nova_auth_api/` owns token verify/introspect behavior.
- `packages/nova_dash_bridge/` owns framework integration only.
- `packages/contracts/` owns OpenAPI artifacts, fixtures, and generated-client
  contract inputs.

Without explicit boundaries, bridge code and app wrappers accumulate duplicate
models, config logic, and runtime behavior.

## Alternatives and scored decision

### Criteria and weights

- Solution leverage: 35%
- Application value: 30%
- Maintenance and cognitive load: 25%
- Architectural adaptability: 10%

### Option scores

| Option | Weighted score (/10) |
| --- | ---: |
| A. Keep app wrappers, runtime packages, and bridge package free to share responsibilities informally | 6.1 |
| B. Enforce package-first runtime ownership with thin wrappers and adapter-only bridge surfaces | **9.6** |
| C. Split the runtime back into multiple repos before final release | 5.4 |

Threshold policy: only options `>= 9.0` are accepted.

## Decision

Choose **Option B**.

### Required characteristics

1. `apps/*` contain bootstrapping, process wiring, and no domain authority.
2. `packages/nova_file_api/` owns:
   - canonical `/v1/transfers/*` and `/v1/jobs*` runtime behavior
   - capability, release-info, liveness, readiness, and metrics handlers
   - transfer, jobs, cache, idempotency, and activity orchestration
3. `packages/nova_auth_api/` owns:
   - `/v1/token/verify`
   - `/v1/token/introspect`
   - token principal mapping and auth failure envelopes
4. `packages/nova_dash_bridge/` may provide framework extraction and glue, but
   it must not redefine Nova API models, endpoint ownership, auth semantics, or
   policy rules.
5. `packages/contracts/` is the only OpenAPI contract artifact authority.
6. Deployment workflows and CI/CD contracts belong to separate deploy-governance
   docs, not this runtime boundary decision.

## Consequences

### Positive

- Code review can reject duplicate runtime authority at package boundaries.
- Bridge refactors have a clear target: reuse core contracts and services.
- Runtime docs map directly to the repository layout operators see on disk.

### Trade-offs

- Convenience shortcuts inside bridge and app layers must be removed.
- Some integration helpers need explicit dependency boundaries instead of
  ambient settings mutation.

## Explicit non-decisions

- No second contract authority inside `nova_dash_bridge`.
- No app-wrapper business logic ownership.
- No runtime ownership claims in CI/CD workflow docs.

## Changelog

- 2026-03-05: Restored `ADR-0025` to runtime boundary ownership and moved
  reusable-workflow governance to `ADR-0031`.
