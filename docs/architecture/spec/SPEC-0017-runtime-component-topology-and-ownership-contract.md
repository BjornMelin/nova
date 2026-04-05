---
Spec: 0017
Title: Runtime component topology and ownership contract
Status: Active
Version: 2.5
Date: 2026-03-22
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0027: Public API v2](./SPEC-0027-public-api-v2.md)"
  - "[requirements.md](../requirements.md)"
---

## 1. Scope

Defines the canonical runtime component map, ownership rules, and allowed
cross-package boundaries for the Nova monorepo.

## 2. Canonical runtime topology

### 2.1 Runtime packages

| Path | Canonical ownership |
| --- | --- |
| `packages/nova_file_api/` | File-transfer routes, export routes, capability/release endpoints, health/readiness, metrics summary, transfer/export/idempotency/activity orchestration, and canonical ASGI entrypoint |
| `packages/nova_runtime_support/` | Internal shared helpers for outer-ASGI request context, request-id propagation, canonical FastAPI exception registration, canonical error-envelope shaping, log redaction, shared auth claim normalization, shared metrics/logging setup, and shared transfer config contracts |
| `packages/nova_dash_bridge/` | Browser/Dash uploader assets and component helpers over canonical Nova HTTP routes |
| `packages/contracts/` | OpenAPI artifacts, fixtures, and generated-client contract inputs |

## 3. Ownership boundaries

1. Runtime HTTP contract ownership stays in the runtime packages plus
   `packages/contracts/openapi/**`.
2. `packages/nova_file_api/` owns the transfer/export/session/quota/copy domain
   modules and persistence helpers used by both the API runtime and workflow
   task handlers.
3. `nova_dash_bridge` is an adapter package. It may:
   - ship packaged browser assets
   - render Dash component shells for browser-backed transfer flows
   - forward bearer auth context into canonical Nova HTTP requests
   - call canonical Nova services through generated or thin HTTP clients
4. `nova_dash_bridge` must not:
   - provide FastAPI or Flask transfer-route adapters
   - define alternate endpoint paths
   - redefine Nova error envelopes
   - become the source of truth for auth policy or storage rules
   - recreate an in-process runtime seam inside the bridge package
5. `packages/nova_workflows/` owns workflow settings and runtime assembly. It
   may import pure transfer/export domain modules from `nova_file_api`, but it
   must not import the API app factory, route modules, or shared HTTP
   transport glue.
6. Runtime packages own process bootstrap; release-only service Dockerfiles must
   stay outside workspace package paths so container-only edits do not trigger
   package version planning.

## 4. Runtime interaction contract

1. `nova_file_api` may depend on `packages/contracts` artifacts.
2. `nova_workflows` may depend on pure `nova_file_api` domain/runtime modules
   for export execution, but not on API transport or route surfaces.
3. `nova_dash_bridge` depends on canonical runtime contracts through
   generated Python SDK packages or direct HTTP integration, not on handwritten
   contract forks or direct runtime-internal imports.
4. Standalone FastAPI apps that need canonical Nova request-id/error-envelope
   behavior must install `nova_runtime_support` directly; `nova_dash_bridge`
   does not own an embedded FastAPI route surface.
5. Route literals remain governed by the canonical route-authority specs; this
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
2. Runtime package ownership statements in README, AGENTS, PRD, requirements,
   plan, runbooks, and architecture indexes align with this package map.
3. Active operator authority IDs and paths must be truthful, resolvable, and
   synchronized across README, AGENTS, plan, PRD, runbooks, and architecture
   indexes.
4. Bridge and runtime-package docs do not claim conflicting route, contract, or
   auth-policy authority.
5. Bridge docs describe browser/Dash helpers only, not embedded server
   adapters.

## 7. Traceability

- [FR-0001](../requirements.md#fr-0001-async-job-endpoints-and-orchestration)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0105](../requirements.md#nfr-0105-contract-traceability)
- [IR-0000](../requirements.md#ir-0000-nova-local-runtime-and-release-authority)
