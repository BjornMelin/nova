---
Spec: 0030
Title: SDK generation and package layout
Status: Active
Version: 1.0
Date: 2026-03-25
Supersedes: ""
Related:
  - "[requirements-wave-2.md](../requirements-wave-2.md)"
  - "[ADR-0037: Consolidate SDK generation and package layout](../adr/ADR-0037-sdk-generation-consolidation.md)"
  - "[Canonical client package layout](../../clients/CLIENT-SDK-CANONICAL-PACKAGES.md)"
  - "[Breaking changes v2](../../contracts/BREAKING-CHANGES-V2.md)"
References:
  - "[Dependency leverage audit](../../overview/DEPENDENCY-LEVERAGE-AUDIT.md)"
  - "[Green-field wave 2 execution plan](../../plan/GREENFIELD-WAVE-2-EXECUTION.md)"
---

## 1. Purpose

Define the approved target-state SDK packaging and generation model for
TypeScript, Python, and R.

## 2. Goals

- one package per language
- no auth/file package splits
- no bespoke TypeScript runtime package
- generated code is treated as generated code, not hand-maintained source

## 3. TypeScript

- generator: `@hey-api/openapi-ts`
- output: generated SDK plus models
- package dir: `packages/nova_sdk_ts`
- the package surface should be small, obvious, and free of bespoke runtime glue
- the active workspace remains on the verified TypeScript 5.x line
- TypeScript 6 remains deferred until the repo-wide migration updates generated
  SDK output, conformance fixtures, and release/docs references together

## 4. Python

- generator: `openapi-python-client`
- output: generated package with minimal template overrides
- package dir: `packages/nova_sdk_py`
- release tooling should orchestrate generation, not patch large parts of the
  output tree

## 5. R

- implementation: thin `httr2` wrapper package
- package dir: `packages/nova_sdk_r`
- do not use OpenAPI Generator R as the canonical path

## 6. Release rule

Release scripts must become small orchestration entrypoints rather than large
patch-and-repair systems that compensate for old package splits.

## 7. Traceability

- [Product requirements](../requirements-wave-2.md#product-requirements)
- [Architecture requirements](../requirements-wave-2.md#architecture-requirements)
- [Repo requirements](../requirements-wave-2.md#repo-requirements)
