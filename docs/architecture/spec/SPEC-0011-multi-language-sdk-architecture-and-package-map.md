---
Spec: 0011
Title: Multi-language SDK architecture and package map
Status: Active
Version: 3.0
Date: 2026-03-07
Related:
  - "[ADR-0013: Multi-language SDK topology uses generated contract-core clients with retained TS/R foundations](../adr/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
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

Defines the Nova SDK package map and target public-SDK posture. Nova must
provide complete public SDKs for Python, TypeScript, and R. Current Python SDK
trees and retained TypeScript/R scaffolding remain generated from the same
canonical OpenAPI artifacts.

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

### 3.2 Python SDK surfaces

- `nova_sdk_py_file` (generated): file-transfer API client and models.
- `nova_sdk_py_auth` (generated): auth API verify/introspect client and models.
- `nova_dash_bridge` (thin adapter): Dash/Flask/FastAPI request extraction,
  authorization-header forwarding, request-id propagation, framework glue only.

Consumer mapping:

- `dash-pca` consumes generated Python SDK packages plus thin bridge utilities.
- No handwritten Python verify client remains authoritative in consumer repos.

### 3.3 TypeScript SDK foundations

- `@nova/sdk-file-core` (generated types and operation signatures from OpenAPI)
- `@nova/sdk-auth-core` (generated auth operation types/signatures)
- `@nova/sdk-fetch` (generator-owned runtime helper over the fetch runtime)

Repository package paths:

- `packages/nova_sdk_file_core/`
- `packages/nova_sdk_auth_core/`
- `packages/nova_sdk_fetch/`

Current status:

- retained in-repo foundation for the target public TypeScript SDK surface
- shared runtime/helpers remain generator-owned
- source installs must work through the repo npm workspace while staged/private
  publication to CodeArtifact emits concrete semver dependencies
- `@nova/sdk-file-core` and `@nova/sdk-auth-core` preserve the public helper
  contract `buildOperationUrl(baseUrl, pathTemplate, pathParams?, queryParams?)`
- descriptor-based URL construction stays in `@nova/sdk-fetch` under a distinct
  helper surface (`buildOperationDescriptorUrl`)
- must stay deterministic and must not be deleted

### 3.4 R SDK foundations

- `nova.sdk.r.file` (generated client bindings/models)
- `nova.sdk.r.auth` (generated auth bindings/models)

Repository package paths:

- `packages/nova_sdk_r_file/`
- `packages/nova_sdk_r_auth/`

Current status:

- retained in-repo foundation for the target public R SDK surface
- generator-owned wrapper/runtime output remains authoritative
- must stay deterministic and must not be deleted

## 4. Required SDK surface behaviors

Public client SDK packages must support:

- explicit base URL configuration
- configurable timeout
- optional request-id header forwarding
- structured error envelope decoding (`error.code`, `error.message`,
  `error.request_id`)
- typed request/response payload models

Retained TypeScript/R foundations must remain deterministic from the same
OpenAPI inputs while Nova completes publish-ready parity.

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
- canonical error-envelope decoding

## 6. Repository ownership and release boundaries

Nova owns:

- OpenAPI contract source
- generated SDK definitions
- public package governance for Python, TypeScript, and R
- shared generation determinism across all three languages

Consumer repos own:

- app/business/domain logic
- framework wiring
- optional convenience wrappers that do not override SDK contract behavior

## 7. Delivery and artifact publishing requirements

- Canonical OpenAPI artifacts are exported and committed before SDK generation.
- Python SDK packages are versioned and published from Nova CI today.
- `scripts/release/generate_clients.py` is the deterministic generator entry
  point for retained TypeScript and R package foundations.
- `scripts/release/generate_python_clients.py` is the deterministic generator
  entry point for committed Python SDK package trees.
- Internal-only operations marked `x-nova-sdk-visibility: internal` remain in
  canonical OpenAPI but are excluded from client SDK generation.

## 8. Traceability

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)
