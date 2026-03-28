# ADR-0037 -- Consolidate SDK generation and package layout

> **Implementation state:** Approved target-state ADR. The current repo may still contain split SDK packages and bespoke TS runtime glue until the implementation branches land.

## Status
Accepted

## Decision

Adopt one canonical SDK package per language:

- TS: `packages/nova_sdk_ts` using `@hey-api/openapi-ts`
- Python: `packages/nova_sdk_py` using `openapi-python-client`
- R: `packages/nova_sdk_r` using a thin `httr2` wrapper

Delete auth SDK packages and delete `packages/nova_sdk_fetch`.

## Context

The attached repo still carries split auth/file SDK packages and a bespoke TypeScript runtime package.

## Why this wins

- fewer packages
- cleaner client discovery
- less release machinery
- better alignment with current ecosystem tools

## Consequences

- rename packages
- simplify release scripts
- simplify examples and docs
