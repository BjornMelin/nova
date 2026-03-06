---
Spec: 0011
Title: Python-first SDK architecture and deferred TS/R package map
Status: Active
Version: 2.1
Date: 2026-03-06
Related:
  - "[ADR-0013: Python-first SDK topology uses generated contract-core clients and defers TS/R productization](../adr/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
  - "[ADR-0002: OpenAPI as contract and SDK generation](../adr/ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0007: Auth API contract](./SPEC-0007-auth-api-contract.md)"
  - "[Plan Master](../../plan/PLAN.md)"
References:
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[openapi-fetch](https://openapi-ts.dev/openapi-fetch/)"
  - "[OpenAPI Generator typescript-fetch](https://openapi-generator.tech/docs/generators/typescript-fetch/)"
---

## 1. Scope

Defines the current-wave Nova SDK package map. Python is the only release-grade
public SDK surface. TypeScript and R packages remain internal/generated catalogs
until a later promotion wave.

This spec governs generated SDK trees and thin adapter surfaces. Runtime
implementation distributions such as `nova_file_api` and `nova_auth_api` are
outside this SDK map even when they publish installed-package typing metadata
(`py.typed`).

## 2. Canonical topology

### 2.1 Core rule

All generated SDK artifacts must originate from canonical OpenAPI artifacts
owned by Nova.

Canonical OpenAPI artifacts must expose stable SDK-facing metadata:

- snake_case `operationId` values that are unique and not path/method-derived
- semantic tags used as generated client/module group boundaries
- named component schemas for custom request bodies referenced from operations

### 2.2 Adapter rule

Thin adapters may exist for language or framework ergonomics, but they must not
introduce protocol or contract authority.

Prohibited in adapters:

- endpoint path ownership
- custom schema forks
- semantic remapping of status/error contracts
- alternate auth decision logic

## 3. Package map

### 3.1 Contracts source

- `packages/contracts/openapi/nova-file-api.openapi.json`
- `packages/contracts/openapi/nova-auth-api.openapi.json`

These are the only generation inputs.

### 3.2 Public release-grade Python surfaces

- `nova_sdk_py_file` (generated): file-transfer API client and models.
- `nova_sdk_py_auth` (generated): auth API verify/introspect client and models.
- `nova_dash_bridge` (thin adapter): Dash/Flask/FastAPI request extraction,
  authorization-header forwarding, request-id propagation, framework glue only.

Consumer mapping:

- `dash-pca` consumes generated Python SDK packages plus thin bridge utilities.
- No handwritten Python verify client remains authoritative in consumer repos.

### 3.3 Internal/generated TypeScript catalogs

- `@nova/sdk-file-core` (generated types and operation signatures from OpenAPI)
- `@nova/sdk-auth-core` (generated auth operation types/signatures)
- `@nova/sdk-fetch` (generator-owned runtime helper over `openapi-fetch`)

Repository package paths:

- `packages/nova_sdk_file_core/`
- `packages/nova_sdk_auth_core/`
- `packages/nova_sdk_fetch/`

Current status:

- internal/generated catalog only
- not a release-grade public SDK surface
- not yet covered by public package publishing/support guarantees

### 3.4 Internal/generated R catalogs

- `nova.sdk.r.file` (generated client bindings/models)
- `nova.sdk.r.auth` (generated auth bindings/models)

Repository package paths:

- `packages/nova_sdk_r_file/`
- `packages/nova_sdk_r_auth/`

Current status:

- internal/generated catalog only
- not a release-grade public SDK surface
- not yet covered by public package publishing/support guarantees

## 4. Required SDK surface behaviors

Public Python SDK packages must support:

- explicit base URL configuration
- configurable timeout
- optional request-id header forwarding
- structured error envelope decoding (`error.code`, `error.message`,
  `error.request_id`)
- typed request/response payload models

Internal TS/R catalogs must remain deterministic from the same OpenAPI inputs
but are not public compatibility authority in this wave.

## 5. Auth contract surface

The canonical SDK auth operation remains `POST /v1/token/verify` with:

- `access_token` (required)
- `required_scopes` (optional)
- `required_permissions` (optional)

Failure handling must preserve upstream status classes:

- `401` authentication failures
- `403` authorization failures
- deterministic fail-closed mapping for transport timeouts or unavailable
  upstreams

## 6. Repository ownership and release boundaries

Nova owns:

- OpenAPI contract source
- generated SDK definitions
- Python public package governance
- TS/R internal catalog generation determinism

Consumer repos own:

- app/business/domain logic
- framework wiring
- optional convenience wrappers that do not override SDK contract behavior

## 7. Delivery and artifact publishing requirements

- Canonical OpenAPI artifacts are exported and committed before SDK generation.
- Python SDK packages are versioned and published from Nova CI.
- `scripts/release/generate_clients.py` is the deterministic generator entry
  point for internal TypeScript and R operation catalogs.
- `scripts/release/generate_python_clients.py` is the deterministic generator
  entry point for committed Python SDK package trees.
- TS/R generated artifacts must stay deterministic in CI, but public
  publishing/promotion is deferred to a later wave.

## 8. Traceability

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)
