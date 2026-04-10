---
Spec: 0017
Title: Runtime component topology and ownership contract
Status: Active
Version: 2.8
Date: 2026-04-10
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0027: Public API v2](./SPEC-0027-public-api-v2.md)"
  - "[SPEC-0030: SDK generation and package layout](./SPEC-0030-sdk-generation-and-package-layout.md)"
  - "[SPEC-0012: SDK conformance, versioning, and compatibility governance](./SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
  - "[requirements.md](../requirements.md)"
---

## 1. Scope

Defines the canonical runtime component map, ownership rules, and allowed
cross-package boundaries for the Nova monorepo.

## 2. Canonical runtime topology

### 2.1 Runtime packages

| Path | Canonical ownership |
| --- | --- |
| `packages/nova_file_api/` | File-transfer routes, export routes, capability/release endpoints, health/readiness, metrics summary, the public `create_app(runtime=...)` and `create_managed_app()` assembly seams, the typed `ApiRuntime` container stored at `app.state.runtime`, request-level application coordinators below the route boundary, and the transfer/export/session/quota/copy domain modules and persistence helpers consumed by API and workflow runtimes |
| `packages/nova_workflows/` | Workflow settings, task-handler runtime assembly, and export orchestration over pure `nova_file_api` domain/runtime surfaces and the shared `nova_file_api.workflow_facade` bridge for workflow-safe imports such as AWS client-config helpers |
| `packages/nova_runtime_support/` | Internal shared helpers for outer-ASGI request context, request-id propagation, canonical FastAPI exception registration, canonical error-envelope shaping, log redaction, shared auth claim normalization, shared metrics/logging setup, and shared transfer config contracts |
| `packages/nova_dash_bridge/` | Browser/Dash uploader assets and component helpers over canonical Nova HTTP routes |
| `packages/contracts/` | Full/runtime and reduced-public OpenAPI artifacts, fixtures, and generated-client contract inputs |

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
   may import pure transfer/export domain modules from `nova_file_api` and the
   explicitly exported workflow facade, but it must not import the API app
   factory, route modules, or shared HTTP transport glue.
6. Runtime packages own process bootstrap; release-only service Dockerfiles must
   stay outside workspace package paths so container-only edits do not trigger
   package version planning.

## 4. Runtime interaction contract

1. `nova_file_api` may depend on `packages/contracts` artifacts.
2. `nova_workflows` may depend on pure `nova_file_api` domain/runtime modules
   and the `nova_file_api.workflow_facade` export surface for export
   execution, but not on API transport or route surfaces.
3. `nova_dash_bridge` depends on canonical runtime contracts through
   generated Python SDK packages or direct HTTP integration, not on handwritten
   contract forks or direct runtime-internal imports.
4. Standalone FastAPI apps that need canonical Nova request-id/error-envelope
   behavior must install `nova_runtime_support` directly; `nova_dash_bridge`
   does not own an embedded FastAPI route surface.
5. Route literals remain governed by the canonical route-authority specs; this
   spec governs where those routes are implemented and owned.

## 5. SDK and bridge relationship

1. Nova owns one canonical generated package per language: public Python and
   release-grade TypeScript packages plus the first-class internal R package.
2. `nova_dash_bridge` remains a Python integration surface and must track the
   canonical Python contract surface without introducing alternate mount
   prefixes.
3. TypeScript is an active release-grade SDK surface. R remains an internal
   first-class package surface with generated-contract governance, but it is
   not a separate runtime authority.
4. Canonical OpenAPI artifact ownership remains the sole SDK authority for
   generated contract surfaces: the full runtime export remains the runtime/API
   machine contract, while the committed reduced public artifact is the SDK
   generation source of truth.
5. Internal-only operations remain documented in the full runtime OpenAPI
   artifact and are excluded from public client SDK generation.

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
6. Active docs describe the public runtime seam as `create_app(runtime=...)`
   plus `create_managed_app()`, with `app.state.runtime` as the only live app
   runtime container slot.

## 7. Traceability

- [Functional requirements](../requirements.md#functional-requirements)
- [Quality requirements](../requirements.md#quality-requirements)
- [Release and automation requirements](../requirements.md#release-and-automation-requirements)
