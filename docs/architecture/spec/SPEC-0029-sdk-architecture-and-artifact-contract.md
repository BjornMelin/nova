---
Spec: 0029
Title: SDK architecture and artifact contract
Status: Active
Version: 1.0
Date: 2026-03-19
Related:
  - "[ADR-0038: Green-field SDK architecture by language](../adr/ADR-0038-sdk-architecture-by-language.md)"
  - "[ADR-0013: Final-state SDK topology](../adr/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
  - "[SPEC-0011: Multi-language SDK architecture and package map](./SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
  - "[SPEC-0012: SDK conformance, versioning, and compatibility governance](./SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
  - "[requirements.md](../requirements.md)"
---

## 1. Purpose

Define the **target** per-language SDK architecture and published artifacts
after the green-field program ([ADR-0038](../adr/ADR-0038-sdk-architecture-by-language.md)).

This SPEC **implements** the topology intent of
[ADR-0013](../adr/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)
and **must remain aligned** with
[SPEC-0011](./SPEC-0011-multi-language-sdk-architecture-and-package-map.md) and
[SPEC-0012](./SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md).

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
- **No** repo-private generic fetch runtime package (for example legacy
  `@nova/sdk-fetch` patterns are removed).
- **Do not** add `zod`, validator packages, validator subpaths, or runtime
  request/response validation helpers to generated TypeScript SDKs.
- Honor declared request media types with explicit generated `contentType`
  selection for multi-media bodies.
- Operations marked `x-nova-sdk-visibility: internal` remain excluded from public
  SDK generation.

## 4. Python

- Generator: **`openapi-python-client`**.
- Customization lives in generator **config** and **minimal templates**.
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

## 7. Traceability

- [GFR-R6](../requirements.md#gfr-r6--sdks-must-feel-native-per-language)
- [GFR-R8](../requirements.md#gfr-r8--one-client-artifact-family-per-language)
- [GFR-R9](../requirements.md#gfr-r9--deterministic-build-and-verification)

## Changelog

- 2026-03-19: Initial canonical SPEC; ports green-field pack SPEC-0003 with
  explicit SPEC-0011/SPEC-0012 alignment.
