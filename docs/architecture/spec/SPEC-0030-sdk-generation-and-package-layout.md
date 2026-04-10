---
SPEC: 0030
Title: SDK generation and package layout
Status: Implemented
Version: 1.1
Date: 2026-04-10
Related:
  - "[ADR-0033: Canonical serverless platform](../adr/ADR-0033-canonical-serverless-platform.md)"
  - "[ADR-0037: Consolidate SDK generation and package layout](../adr/ADR-0037-sdk-generation-consolidation.md)"
  - "[SPEC-0012: SDK governance for Python public, release-grade TypeScript, and first-class internal R packages](./SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
---

## Goals

- one package per language
- no auth/file package splits
- no bespoke TS runtime
- generated code treated as generated code, not hand-maintained source

## OpenAPI artifact authority

- Full runtime export:
  `packages/contracts/openapi/nova-file-api.openapi.json`
- Reduced public SDK artifact:
  `packages/contracts/openapi/nova-file-api.public.openapi.json`

The reduced public artifact is the committed SDK-generation source of truth for
TypeScript, Python, and R. The full runtime export remains the runtime/API
contract authority.

## TypeScript

- generator: `@hey-api/openapi-ts`
- source artifact: `packages/contracts/openapi/nova-file-api.public.openapi.json`
- output: generated SDK + models
- package dir: `packages/nova_sdk_ts`

## Python

- generator: `openapi-python-client`
- source artifact: `packages/contracts/openapi/nova-file-api.public.openapi.json`
- output: generated package with minimal template overrides
- package dir: `packages/nova_sdk_py`

## R

- implementation: thin `httr2` wrapper package
- source artifact: `packages/contracts/openapi/nova-file-api.public.openapi.json`
- package dir: `packages/nova_sdk_r`
- installed package: `nova`
- exported helpers remain part of the public package surface

## Release rule

Release scripts must become small orchestration entrypoints, not giant patching systems.
They should orchestrate generator-owned behavior around the committed public
artifact rather than reimplement public-surface reduction in language-specific
lanes. Generated TypeScript and Python outputs must fail when unresolved
TODO/FIXME/XXX markers remain in committed output.
