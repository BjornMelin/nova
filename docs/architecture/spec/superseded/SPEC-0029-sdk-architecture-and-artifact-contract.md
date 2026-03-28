> **Superseded target draft**
>
> This draft was superseded before implementation by `SPEC-0030-sdk-generation-and-package-layout.md`.

---
Spec: 0029
Title: SDK architecture and artifact contract
Status: Superseded
Version: 1.2
Date: 2026-03-22
Supersedes: "[SPEC-0011: Multi-language SDK architecture and package map (superseded)](./superseded/SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0038: Green-field SDK architecture by language](../adr/ADR-0038-sdk-architecture-by-language.md)"
  - "[ADR-0013: Final-state SDK topology (superseded)](../adr/superseded/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
  - "[SPEC-0012: SDK conformance, versioning, and compatibility governance](./SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
---

## 1. Purpose

Define the **target** per-language SDK architecture and published artifacts
after the green-field program ([ADR-0038](../adr/ADR-0038-sdk-architecture-by-language.md)).

This SPEC **implements** the topology intent of
[ADR-0013](../adr/superseded/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)
and is the active successor to superseded
[SPEC-0011](./superseded/SPEC-0011-multi-language-sdk-architecture-and-package-map.md).
[SPEC-0012](./SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)
remains the authority for conformance, versioning, and compatibility governance.

## 2. Artifacts

- One Python SDK package (public contract core).
- One TypeScript SDK package (release-grade; generator-owned; subpath-only
  exports; **no** package-root `"."` exports).
- One R SDK package (first-class internal release line).
- One canonical public OpenAPI artifact for the file API.
- **Zero** auth-only SDK packages.

## 3. TypeScript

- Type source: **`openapi-typescript`**.
- Runtime transport: **`openapi-fetch`**.
- The active repo baseline keeps the npm workspace on the verified TypeScript
  5.x line under Node 24 LTS. TypeScript 6 remains deferred until a dedicated
  repo-wide migration updates generated SDK output, conformance fixtures, and
  release/workflow docs together.
- **No** repo-private generic fetch runtime package (for example legacy
  `@nova/sdk-fetch` patterns are removed).
- **Do not** add `zod`, validator packages, validator subpaths, or runtime
  request/response validation helpers to generated TypeScript SDKs.
- Honor declared request media types with explicit generated `contentType`
  selection for multi-media bodies.
- When present, operations marked `x-nova-sdk-visibility: internal` remain
  excluded from public SDK generation. This is a generator-governance rule and
  may be absent from the canonical public file API OpenAPI artifact.

## 4. Python

- Generator: **`openapi-python-client`**.
- Exact generator pin: **`openapi-python-client==0.28.3`**.
- Customization lives in generator **config** and **minimal templates**.
- Committed Python generator assets live under
  `scripts/release/openapi_python_client/`.
- The committed package root may retain hand-maintained packaging metadata, but
  the generated module tree under `packages/nova_sdk_py_file/src/` is owned by
  `scripts/release/generate_python_clients.py`.
- Large output patching scripts are not allowed unless clearly justified and
  reviewed.

## 5. R

- Client built around **`httr2`**.
- Package ergonomics optimized for Shiny and analytics users.
- Avoid a large custom request-runtime interpreter; prefer thin helpers plus
  minimal generated operation metadata.

## 6. Conformance

- Generated artifacts must be **reproducible**.
- Build, typecheck, and smoke-check commands remain in CI.
- Docs and examples must track the final artifact surface.

## 7. Package map and repository layout (target)

### 7.1 Contracts source

- `packages/contracts/openapi/nova-file-api.openapi.json` is the canonical
  public OpenAPI artifact for SDK generation inputs.

### 7.2 Python

- One generated public file client package (for example `nova_sdk_py_file`).
- `nova_dash_bridge` remains a thin adapter: framework glue and header
  forwarding only; it calls the async-first `nova_file_api.public` seam and
  must not own route, auth, or alternate in-process contract authority.

### 7.3 TypeScript

- One release-grade generated package (for example `@nova/sdk-file`) with
  explicit subpath exports (`client`, `types`, `operations`, `errors`, and
  similar generator-owned surfaces).
- `types` subpaths expose curated operation helpers and reachable public schema
  aliases only; raw whole-spec OpenAPI aliases are not public contract surface.

### 7.4 R

- One first-class internal release package (for example `nova.sdk.r.file`).
- Logical format `r`, CodeArtifact generic transport, tarball plus detached
  `.sig`, with release evidence recording `tarball_sha256` and
  `signature_sha256`.
- The generated package stays thin: concrete OpenAPI path/query parameters in
  public wrappers, bearer-token auth through the constructor and request
  headers, and JSON request/response handling for the current public file API.

## 8. Required client behaviors

Public Python, TypeScript, and R SDKs must support:

- explicit base URL configuration
- configurable timeout
- optional request-id header forwarding
- OpenAPI-aligned request-body serialization for the media types declared by each
  public operation
- structured error envelope decoding (`error.code`, `error.message`,
  `error.request_id`)
- typed request/response payload models

Error compatibility is defined by the `ErrorEnvelope` response schema name and
the on-wire nested fields under `error`; subordinate component names, `$ref`
layout, and generator-emitted helper model names are not compatibility
guarantees.

TypeScript: single-media bodies may use generator-supplied default media types;
multi-media bodies must expose explicit generated `contentType` selection when
the wire format would otherwise be ambiguous.

R: preserve OpenAPI-driven wire behavior with package-native constructors,
namespace generation, deterministic tarball evidence across releases, and
public wrappers that expose concrete OpenAPI path/query parameters rather than
generic request-bag arguments.

## 9. Auth contract surface (public SDKs)

Public callers authenticate with **bearer JWT** verified in the file API
runtime per
[SPEC-0027](./SPEC-0027-public-http-contract-revision-and-bearer-auth.md).
There is **no** generated client surface for `POST /v1/token/verify`,
`POST /v1/token/introspect`, or other retired dedicated-auth routes.

## 10. Repository ownership and delivery

Nova owns OpenAPI contract sources, generated SDK definitions, and release
governance for Python public, TypeScript CodeArtifact, and R internal packages.

Consumer repos own application logic, framework wiring, and optional wrappers
that do not override SDK contract behavior.

- Canonical OpenAPI artifacts are exported and committed before SDK generation.
- `scripts/release/generate_clients.py` is the deterministic generator entry
  point for TypeScript SDK artifacts and R package sources.
- `scripts/release/generate_python_clients.py` is the deterministic generator
  entry point for committed Python SDK package trees.
- TypeScript artifacts must stay deterministic in CI and retain published
  subpath contracts.
- R package sources and tarball evidence must stay deterministic in CI and be
  promoted through CodeArtifact generic packages.

## 11. Traceability

- [GFR-R6](../requirements.md#gfr-r6--sdks-must-feel-native-per-language)
- [GFR-R8](../requirements.md#gfr-r8--one-client-artifact-family-per-language)
- [GFR-R9](../requirements.md#gfr-r9--deterministic-build-and-verification)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)

## Changelog

- 2026-03-19: v1.1 -- Active successor to SPEC-0011; add package map, client
  behaviors, ownership/delivery, and bearer-only auth surface for SDKs.
- 2026-03-19: v1.0 -- Initial canonical SPEC; ports green-field pack SPEC-0003 with
  explicit SPEC-0011/SPEC-0012 alignment.
