---
Spec: 0017
Title: Runtime component topology and ownership contract
Status: Active
Version: 2.0
Date: 2026-03-05
Related:
  - "[ADR-0024: Layered runtime authority pack for the Nova monorepo](../adr/ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0025: Runtime monorepo component boundaries and ownership](../adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](./SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
  - "[SPEC-0018: Runtime configuration and startup validation contract](./SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[SPEC-0019: Auth execution and threadpool safety contract](./SPEC-0019-auth-execution-and-threadpool-safety-contract.md)"
---

## 1. Scope

Defines the canonical runtime component map, ownership rules, and allowed
cross-package boundaries for the Nova monorepo.

## 2. Canonical runtime topology

### 2.1 Service wrappers

| Path | Role | Prohibited responsibilities |
| --- | --- | --- |
| `apps/nova_file_api_service/` | ASGI boot wrapper for file API runtime | Domain logic, route semantics, auth policy, request/response model authority |
| `apps/nova_auth_api_service/` | ASGI boot wrapper for auth API runtime | Token semantics, principal mapping, auth error policy |

### 2.2 Runtime packages

| Path | Canonical ownership |
| --- | --- |
| `packages/nova_file_api/` | File-transfer routes, job routes, internal worker result route, capability/release endpoints, health/readiness, metrics summary, transfer/jobs/cache/idempotency/activity orchestration |
| `packages/nova_auth_api/` | Token verify/introspect routes, verifier lifecycle, principal normalization, auth API envelopes |
| `packages/nova_dash_bridge/` | Dash/Flask/FastAPI integration helpers over canonical Nova contracts |
| `packages/contracts/` | OpenAPI artifacts, fixtures, and generated-client contract inputs |

## 3. Ownership boundaries

1. Runtime HTTP contract ownership stays in the runtime packages plus
   `packages/contracts/openapi/**`.
2. `nova_dash_bridge` is an adapter package. It may:
   - extract framework request metadata
   - forward headers and request identifiers
   - call canonical Nova services or generated clients
3. `nova_dash_bridge` must not:
   - define alternate endpoint paths
   - redefine Nova error envelopes
   - become the source of truth for auth policy or storage rules
4. App wrappers may wire lifespan, middleware, and process bootstrap only.

## 4. Runtime interaction contract

1. `nova_file_api` and `nova_auth_api` may depend on `packages/contracts`
   artifacts.
2. `nova_dash_bridge` depends on canonical runtime contracts or generated
   Python SDK packages, not on handwritten contract forks.
3. Route literals remain governed by `SPEC-0000` and `SPEC-0016`; this spec
   governs where those routes are implemented and owned.

## 5. SDK and bridge relationship

1. Release-grade public SDK ownership for this wave is Python-only.
2. `nova_dash_bridge` remains a Python integration surface and must track the
   canonical Python contract surface.
3. TypeScript and R generated catalogs may exist in-repo, but they do not own
   runtime semantics and are not part of the release-grade public runtime
   surface in this wave.

## 6. Acceptance criteria

1. Active authority docs describe runtime package topology instead of
   deploy-control-plane modules.
2. Runtime/app ownership statements in README, PRD, requirements, plan, and
   runbooks align with this package map.
3. Bridge and app-wrapper docs do not claim route, contract, or auth-policy
   authority.

## 7. Traceability

- [FR-0001](../requirements.md#fr-0001-async-job-endpoints-and-orchestration)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
