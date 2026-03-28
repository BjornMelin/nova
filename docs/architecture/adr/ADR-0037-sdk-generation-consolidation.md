# ADR-0037 -- Consolidate SDK generation and package layout

> **Implementation state:** Implemented in the current repository baseline, with stale split-package references still requiring cleanup from active docs/examples.

## Status
Accepted

## Decision

Adopt one canonical SDK package per language:

- TS: `packages/nova_sdk_ts` using `@hey-api/openapi-ts`
- Python: `packages/nova_sdk_py` using `openapi-python-client`
- R: `packages/nova_sdk_r` using a thin `httr2` wrapper

Keep auth SDK packages and `packages/nova_sdk_fetch` out of the active package
surface.

## Context

The current repository already uses one SDK package per language, but some
docs/examples still need retirement cleanup so they stop describing the older
split auth/file package posture.

## Why this wins

- fewer packages
- cleaner client discovery
- less release machinery
- better alignment with current ecosystem tools

## Consequences

- keep canonical package names in release scripts, examples, and docs
- keep release scripts small and aligned to generator-owned outputs
- retire stale split-package references from examples and supporting docs
