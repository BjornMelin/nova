# Canonical client package layout

> **Implementation state:** Approved target-state client/package plan. Current package names in the repo may still be pre-cut.


## TypeScript

- Package name: `@nova/sdk`
- Source package directory: `packages/nova_sdk_ts`
- Generator: `@hey-api/openapi-ts`
- Client style: generated fetch client

## Python

- Package name: `nova-sdk-py` (or `nova_sdk_py` import package)
- Source package directory: `packages/nova_sdk_py`
- Generator: `openapi-python-client`
- Output rule: thin templates/config, no huge patch step

## R

- Package name: `novaR` or `nova` based on CRAN naming choice
- Source package directory: `packages/nova_sdk_r`
- Strategy: thin `httr2` wrapper package
- No OpenAPI Generator R output in the canonical repo

## Shared principles

- one client package per language
- one auth model across all clients
- typed models generated where it materially reduces maintenance
- handwritten code only where generators are weaker than the language-native ecosystem
