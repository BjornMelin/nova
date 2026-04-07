---
ADR: 0025
Title: Runtime monorepo component boundaries and ownership
Status: Accepted
Version: 2.7
Date: 2026-04-07
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0027: Public API v2](../spec/SPEC-0027-public-api-v2.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0024: Layered runtime authority pack for the Nova monorepo](./ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0026: Fail-fast runtime configuration and safe auth execution](./ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)"
  - "[SPEC-0017: Runtime component topology and ownership contract](../spec/SPEC-0017-runtime-component-topology-and-ownership-contract.md)"
  - "[SPEC-0018: Runtime configuration and startup validation contract](../spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[SPEC-0019: Auth execution and threadpool safety contract](../spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](./ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
---

## Summary

Nova runtime ownership is package-first. Runtime packages own process
entrypoints, typed runtime assembly, route-boundary request handling,
application-layer orchestration, auth, and worker logic; release-only service
Dockerfiles stay outside workspace package paths so container changes do not
masquerade as package releases. The Dash bridge remains an adapter over
canonical Nova HTTP contracts instead of a second runtime authority.

## Context

The runtime now lives in one monorepo, but the architecture only stays legible
if package ownership remains explicit:

- `packages/nova_file_api/` owns transfer and export control-plane behavior,
  the public app assembly seams, and the single `app.state.runtime`
  `ApiRuntime` container slot.
- `packages/nova_runtime_support/` owns shared cross-cutting runtime transport
  and support helpers only: outer-ASGI request context, canonical FastAPI
  exception registration, auth claim normalization, shared logging/metrics,
  and shared transfer config contracts.
- `packages/nova_dash_bridge/` owns framework integration only.
- `packages/contracts/` owns OpenAPI artifacts, fixtures, and generated-client
  contract inputs.

Without explicit boundaries, bridge code and duplicate service wrappers
accumulate redundant models, config logic, runtime behavior, and release
surface area.

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

1. `packages/nova_file_api/` owns:
   - canonical `/v1/transfers/*` and `/v1/exports*` runtime behavior
   - capability, release-info, liveness, readiness, and metrics handlers
   - thin FastAPI routes that stop at parse/validate/auth/delegate/return
   - request-level `TransferApplicationService` and
     `ExportApplicationService` orchestration for idempotency, metrics, and
     activity concerns below the route boundary
   - transfer, export, cache, idempotency, and activity orchestration
   - export repositories, export copy state, upload-session state, transfer
     quota persistence, and multipart reconciliation helpers
   - in-process bearer JWT verification and principal mapping
   - the public `create_app(runtime=...)` and `create_managed_app()` assembly
     seams
   - the canonical `nova_file_api.main:app` process entrypoint consumed by the
     release-only file-service Dockerfile under `apps/`
   - the canonical Lambda handler path, which bootstraps one process-reused
     `ApiRuntime` container and stores it only at `app.state.runtime`
2. `packages/nova_dash_bridge/` may provide packaged browser assets and Dash
   component glue, but it must not redefine Nova API models, endpoint
   ownership, auth semantics, or policy rules. It consumes the canonical Nova
   HTTP contract instead of keeping an in-process bridge seam alive.
3. `packages/nova_runtime_support/` owns shared outer-ASGI request context,
   request-id propagation, shared FastAPI exception registration, auth-claim
   normalization, structured logging/metrics helpers, and shared transfer
   config contracts. Runtime packages may adapt domain errors, but they do not
   re-implement the cross-cutting transport layer.
4. `packages/nova_workflows/` owns workflow settings and runtime assembly for
   Step Functions task handlers. It may import the pure transfer/export domain
   modules from `packages/nova_file_api/` plus the explicit
   `nova_file_api.workflow_facade` export surface, but it must not depend on
   the app factory, route modules, or HTTP transport layer.
5. `packages/contracts/` is the only OpenAPI contract artifact authority.
6. Deployment workflows and CI/CD contracts belong to separate deploy-governance
   docs, not this runtime boundary decision.

## Consequences

### Positive

- Code review can reject duplicate runtime authority at package boundaries.
- Runtime reviews have one explicit assembly seam: `create_app(runtime=...)`
  or `create_managed_app()`, never ambient `app.state.*` service locators.
- Bridge refactors have a clear target: reuse the canonical Nova HTTP contract
  instead of runtime internals.
- Runtime docs map directly to the repository layout operators see on disk.

### Trade-offs

- Convenience shortcuts inside bridge and duplicate service layers must be removed.
- Some integration helpers need explicit dependency boundaries instead of
  ambient settings mutation.

## Explicit non-decisions

- No second contract authority inside `nova_dash_bridge`.
- No duplicate app-wrapper package layer for service bootstrapping.
- No runtime ownership claims in CI/CD workflow docs.

## Changelog

- 2026-04-07 (v2.7): Folded the explicit `ApiRuntime` bootstrap seam,
  `app.state.runtime` ownership, thin-route application coordinators, and
  workflow-facade import boundary into the accepted runtime package contract.
- 2026-03-22 (v2.3): Added explicit ownership for shared outer-ASGI transport
  and FastAPI exception registration in `nova_runtime_support`.
- 2026-04-04 (v2.6): Hard-cut export/session/quota/workflow domain ownership
  out of `nova_runtime_support`; `nova_workflows` now consumes pure
  `nova_file_api` modules for workflow execution while `nova_runtime_support`
  stays limited to cross-cutting helpers.
- 2026-03-31 (v2.5): Hard-cut `nova_dash_bridge` to browser/Dash helpers only
  and removed the retired in-process bridge seam.
- 2026-03-22 (v2.4): Clarified that the former bridge seam was async-first and
  that retained sync wrappers in `nova_dash_bridge` were explicit edge adapters
  rather than a second canonical surface.
- 2026-03-19 (v2.2): Removed active `nova_auth_api` ownership from the runtime
  boundary contract after the in-process auth cutover landed in `nova_file_api`.
- 2026-03-10 (v2.1): Consolidated service entrypoints into
  `packages/nova_file_api` and `packages/nova_auth_api`, while keeping the
  release-only service Dockerfiles outside workspace package paths.
- 2026-03-05: Restored `ADR-0025` to runtime boundary ownership and moved
  reusable-workflow governance to `ADR-0031`.
