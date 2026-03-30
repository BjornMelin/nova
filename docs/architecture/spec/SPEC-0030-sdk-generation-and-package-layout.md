---
SPEC: 0030
Title: SDK generation and package layout
Status: Implemented
Version: 1.0
Date: 2026-03-25
Related:
  - "[ADR-0033: Canonical serverless platform](../adr/ADR-0033-canonical-serverless-platform.md)"
  - "[ADR-0037: Consolidate SDK generation and package layout](../adr/ADR-0037-sdk-generation-consolidation.md)"
---

## Goals

- one package per language
- no auth/file package splits
- no bespoke TS runtime
- generated code treated as generated code, not hand-maintained source

## TypeScript

- generator: `@hey-api/openapi-ts`
- output: generated SDK + models
- package dir: `packages/nova_sdk_ts`

## Python

- generator: `openapi-python-client`
- output: generated package with minimal template overrides
- package dir: `packages/nova_sdk_py`

## R

- implementation: thin `httr2` wrapper package
- package dir: `packages/nova_sdk_r`
- installed package: `nova`
- exported helpers remain part of the public package surface

## Release rule

Release scripts must become small orchestration entrypoints, not giant patching systems.
