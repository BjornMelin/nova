---
Spec: 0011
Title: Multi-language SDK architecture and package map
Status: Active
Version: 1.0
Date: 2026-02-28
Related:
  - "[ADR-0013: Final-state SDK topology uses generated contract-core clients plus thin language adapters](../adr/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
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

This spec defines the final-state SDK topology and package boundaries for Nova consumers in Python (Dash), TypeScript (Next), and R (Shiny). It covers package ownership, API surfaces, adapter constraints, and integration contracts.

## 2. Canonical topology

### 2.1 Core rule

All language core SDKs MUST be generated from canonical OpenAPI artifacts owned by Nova.

### 2.2 Adapter rule

Thin adapters MAY exist for language/framework ergonomics, but MUST NOT introduce protocol or contract authority.

Prohibited in adapters:

- endpoint path ownership
- custom schema forks
- semantic remapping of status/error contracts
- alternate auth decision logic

## 3. Package map

### 3.1 Contracts source

- `packages/contracts/openapi/nova-file-api.openapi.json`
- `packages/contracts/openapi/nova-auth-api.openapi.json`

These are the only contract generation inputs.

### 3.2 Python surfaces

- `nova_sdk_py_file` (generated): file-transfer API client and models.
- `nova_sdk_py_auth` (generated): auth API verify/introspect client and models.
- `nova_dash_bridge` (thin adapter): Dash/Flask request extraction, authorization-header forwarding, request-id propagation, framework glue only.

Consumer mapping:

- `dash-pca` consumes generated `nova_sdk_py_auth` + `nova_sdk_py_file` through thin bridge utilities.
- No standalone handwritten verify client remains authoritative in consumer repo.

### 3.3 TypeScript surfaces

- `@nova/sdk-file-core` (generated types + generated operation signatures from OpenAPI).
- `@nova/sdk-auth-core` (generated auth operation types/signatures).
- `@nova/sdk-fetch` (thin runtime adapter): wraps `openapi-fetch` client configuration (base URL, headers, retries policy hooks, telemetry hooks).

Consumer mapping:

- `next-analysis-bolt` and `next-analytics` converge on `@nova/sdk-*` packages.
- App-local API clients are wrappers over these packages only.

### 3.4 R surfaces

- `nova.sdk.r.file` (generated client bindings/models).
- `nova.sdk.r.auth` (generated auth bindings/models).
- `shiny-auth-mmm` (thin adapter): session token extraction + reactive integration; delegates HTTP contract behavior to generated client.

Consumer mapping:

- `ShinyAbsorberApp` and `UVAbsorbers` consume `shiny-auth-mmm` thin adapter + generated R SDK packages.

## 4. Required SDK surface behaviors

All generated language cores MUST support:

- explicit base URL configuration
- configurable timeout
- optional request-id header forwarding
- structured error envelope decoding (`error.code`, `error.message`, `error.request_id`)
- typed request/response payload models

All thin adapters MUST support:

- host-framework auth token extraction
- host-framework request context propagation
- no endpoint/schema forks

## 5. Auth contract surface

The auth SDKs MUST expose `POST /v1/token/verify` as first-class operation with:

- `access_token` (required)
- `required_scopes` (optional)
- `required_permissions` (optional)

Failure handling MUST preserve upstream status classes:

- 401 authentication failures
- 403 authorization failures
- deterministic fail-closed mapping for transport timeouts/unavailable upstream

## 6. Repository ownership and release boundaries

Nova owns:

- OpenAPI contract source
- generated SDK definitions
- versioning policy and compatibility gates

Consumer repos own:

- app/business/domain logic
- framework wiring
- optional convenience wrappers that do not override SDK contract behavior

## 7. Delivery and artifact publishing requirements

- SDK artifacts for Python, TypeScript, and R are versioned and published from Nova CI.
- Each release includes machine-readable changelog entries by package.
- Generated artifacts are deterministic from OpenAPI inputs plus pinned generator versions.

## 8. Traceability

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)
