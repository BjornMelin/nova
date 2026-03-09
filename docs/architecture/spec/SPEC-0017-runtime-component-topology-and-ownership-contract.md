---
Spec: 0017
Title: Runtime component topology and ownership contract
Status: Active
Version: 2.1
Date: 2026-03-07
Related:
  - "[ADR-0024: Layered runtime authority pack for the Nova monorepo](../adr/ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0025: Runtime monorepo component boundaries and ownership](../adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0015: Nova API platform final topology and delivery contract](./SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
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
| `packages/nova_runtime_support/` | Internal shared helpers for request IDs, canonical error-envelope OpenAPI shaping, log redaction, and shared auth claim normalization |
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
3. Route literals remain governed by the canonical route-authority specs; this
   spec governs where those routes are implemented and owned.

## 5. SDK and bridge relationship

1. Nova owns the public Python SDK as the sole release-grade public SDK
   authority.
2. `nova_dash_bridge` remains a Python integration surface and must track the
   canonical Python contract surface without introducing alternate mount
   prefixes.
3. TypeScript and R retained scaffolding may exist in-repo, but they are
   non-authoritative and must not be presented as public SDKs.
4. Canonical OpenAPI remains the sole SDK authority for generated contract
   surfaces.
5. Internal-only operations remain documented in canonical OpenAPI and are
   excluded from client SDK generation.

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
