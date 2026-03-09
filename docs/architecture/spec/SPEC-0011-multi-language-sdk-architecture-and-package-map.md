---
Spec: 0011
Title: Public Python SDK architecture with generated/private TypeScript and deferred R package map
Status: Active
Version: 2.0
Date: 2026-03-05
Related:
  - "[ADR-0013: Public Python SDK topology uses generated contract-core clients while TypeScript remains generated/private and R stays deferred](../adr/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
  - "[ADR-0002: OpenAPI as contract and SDK generation](../adr/ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0007: Auth API contract](./SPEC-0007-auth-api-contract.md)"
  - "[Plan Master](../../plan/PLAN.md)"
References:
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[openapi-typescript](https://openapi-ts.dev/introduction)"
  - "[Node.js package entry points / exports](https://nodejs.org/api/packages.html#package-entry-points)"
---

## 1. Scope

Defines the current-wave Nova SDK package map. Python is the release-grade
public SDK surface. TypeScript packages remain generated/private-distribution
artifacts, and R packages remain internal/generated catalogs until later
promotion waves.

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

### 3.3 Generated/private TypeScript SDKs

- `@nova/sdk-file` (generated file SDK with `client`, `types`,
  `operations`, and `errors` subpaths)
- `@nova/sdk-auth` (generated auth SDK with `client`, `types`,
  `operations`, and `errors` subpaths)
- `@nova/sdk-fetch` (generator-owned runtime helper used by the generated SDKs)

Repository package paths:

- `packages/nova_sdk_file/`
- `packages/nova_sdk_auth/`
- `packages/nova_sdk_fetch/`

Current status:

- generated/private-distribution SDK surface
- generated directly from the committed OpenAPI artifacts
- runtime-lean and intentionally free of bundled validation libraries
- `types` subpaths expose curated operation helpers and reachable public
  schema aliases only; raw whole-spec OpenAPI aliases are not public contract
  surface

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

Python public and TypeScript generated SDK packages must support:

- explicit base URL configuration
- configurable timeout
- optional request-id header forwarding
- OpenAPI-aligned request-body serialization for the media types declared by
  each public operation
- structured error envelope decoding (`error.code`, `error.message`,
  `error.request_id`)
- typed request/response payload models

For generated/private TypeScript SDKs specifically:

- single-media request bodies may use generator-supplied default media types
- multi-media request bodies must expose explicit generated `contentType`
  selection when the wire format would otherwise be ambiguous

Internal R catalogs must remain deterministic from the same OpenAPI inputs but
are not public compatibility authority in this wave.

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
- TypeScript generated/private package governance
- R internal catalog generation determinism

Consumer repos own:

- app/business/domain logic
- framework wiring
- optional convenience wrappers that do not override SDK contract behavior

## 7. Delivery and artifact publishing requirements

- Canonical OpenAPI artifacts are exported and committed before SDK generation.
- Python and TypeScript SDK packages are versioned and published from Nova CI.
- `scripts/release/generate_clients.py` is the deterministic generator entry
  point for generated/private TypeScript SDK artifacts and internal R operation
  catalogs.
- `scripts/release/generate_python_clients.py` is the deterministic generator
  entry point for committed Python SDK package trees.
- TypeScript generated artifacts must stay deterministic in CI and retain the
  published subpath contracts.
- R generated artifacts must stay deterministic in CI, but public
  publishing/promotion is deferred to a later wave.

## 8. Traceability

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)
