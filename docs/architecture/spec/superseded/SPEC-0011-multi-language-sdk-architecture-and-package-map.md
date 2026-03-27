---
Spec: 0011
Title: Public Python SDK architecture with release-grade TypeScript and first-class internal R package map
Status: Superseded
Superseded-by: "[SPEC-0029: SDK architecture and artifact contract](../SPEC-0029-sdk-architecture-and-artifact-contract.md)"
Version: 3.0
Date: 2026-03-18
Related:
  - "[Requirements: Nova functional and non-functional requirements](../../requirements.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](../../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[ADR-0013: Final-state SDK topology (superseded)](../../adr/superseded/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
  - "[ADR-0038: Green-field SDK architecture by language](../../adr/ADR-0038-sdk-architecture-by-language.md)"
  - "[ADR-0002: OpenAPI as contract and SDK generation](../../adr/ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0000: HTTP API contract](../SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](../SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0027: Public HTTP contract revision and bearer auth](../SPEC-0027-public-http-contract-revision-and-bearer-auth.md)"
  - "[Plan Master](../../../plan/PLAN.md)"
References:
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[openapi-typescript](https://openapi-ts.dev/introduction)"
  - "[Node.js package entry points / exports](https://nodejs.org/api/packages.html#package-entry-points)"
---

This specification was superseded by
[SPEC-0029](../SPEC-0029-sdk-architecture-and-artifact-contract.md), which is
the active SDK architecture and artifact authority for the green-field program.
[SPEC-0012](../SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)
remains active for conformance, versioning, and compatibility governance.

## 1. Scope

Defines the current-wave Nova SDK package map. Python is the release-grade
public SDK surface. TypeScript packages are release-grade within Nova's
existing CodeArtifact staged/prod system while remaining generator-owned and
subpath-only, and R packages are first-class internal release artifacts with
real package scaffolds, logical format `r`, CodeArtifact generic transport,
and release evidence that records both the tarball and detached `.sig` SHA256
values.

## 2. Canonical topology

### 2.1 Core rule

All generated SDK artifacts must originate from canonical OpenAPI artifacts
owned by Nova.

Canonical OpenAPI artifacts must expose stable SDK-facing metadata:

- explicit snake_case `operationId` values that are unique and frozen by the
  runtime contract tests
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

- legacy split Python file SDK package (generated): file-transfer API client and models.
- legacy split Python auth SDK package (generated): auth API verify/introspect client and models.
- `nova_dash_bridge` (thin adapter): Dash/Flask/FastAPI request extraction,
  authorization-header forwarding, request-id propagation, framework glue only.
  It consumes the canonical in-process transfer seam via `nova_file_api.public`.

Consumer mapping:

- `dash-pca` consumes generated Python SDK packages plus thin bridge utilities.
- No handwritten Python verify client remains authoritative in consumer repos.

### 3.3 Release-grade TypeScript SDKs

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

- release-grade SDK surface within Nova's existing CodeArtifact staged/prod
  system
- generated directly from the committed OpenAPI artifacts
- generator-owned and subpath-only
- runtime-lean and intentionally free of bundled validation libraries
- `types` subpaths expose curated operation helpers and reachable public
  schema aliases only; raw whole-spec OpenAPI aliases are not public contract
  surface

### 3.4 First-class internal R packages

- `nova.sdk.r.file` (real R package exposing generated client bindings/models)
- `nova.sdk.r.auth` (real R package exposing generated auth bindings/models)

Repository package paths:

- `packages/nova_sdk_r_file/`
- `packages/nova_sdk_r_auth/`

Current status:

- first-class internal release artifact line
- real package scaffolds with logical format `r`
- transported through CodeArtifact generic packages as a tarball plus
  detached `.sig`
- accompanied by release evidence that records `tarball_sha256` and
  `signature_sha256`
- not a public SDK surface or public support commitment

## 4. Required SDK surface behaviors

Python public, TypeScript release-grade, and R internal release packages must
support:

- explicit base URL configuration
- configurable timeout
- optional request-id header forwarding
- OpenAPI-aligned request-body serialization for the media types declared by
  each public operation
- structured error envelope decoding (`error.code`, `error.message`,
  `error.request_id`)
- typed request/response payload models

For TypeScript SDKs specifically:

- single-media request bodies may use generator-supplied default media types
- multi-media request bodies must expose explicit generated `contentType`
  selection when the wire format would otherwise be ambiguous

R packages must preserve the same OpenAPI-driven wire contract behavior while
keeping package-native constructors, namespace generation, and tarball
evidence deterministic across releases.

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
- TypeScript CodeArtifact release-line governance
- R internal release package governance and tarball evidence

Consumer repos own:

- app/business/domain logic
- framework wiring
- optional convenience wrappers that do not override SDK contract behavior

## 7. Delivery and artifact publishing requirements

- Canonical OpenAPI artifacts are exported and committed before SDK generation.
- Python and TypeScript SDK packages are versioned and published from Nova CI.
- R packages are built, checked, and released from Nova CI as CodeArtifact
  generic packages carrying the tarball and detached `.sig`.
- `scripts/release/generate_clients.py` is the deterministic generator entry
  point for TypeScript SDK artifacts and R package sources.
- `scripts/release/generate_python_clients.py` is the deterministic generator
  entry point for committed Python SDK package trees.
- TypeScript artifacts must stay deterministic in CI and retain the published
  subpath contracts.
- R package sources and tarball evidence must stay deterministic in CI and be
  promoted through CodeArtifact generic packages.

## 8. Traceability

- [FR-0005](../../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../../requirements.md#ir-0003-optional-remote-auth-service)
