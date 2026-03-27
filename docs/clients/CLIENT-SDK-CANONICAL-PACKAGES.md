# Canonical client package layout

> **Implementation state:** Approved target-state client/package plan. Current package names in the repo may still be pre-cut.

## TypeScript

- Package name: `@nova/sdk`
- Source package directory: `packages/nova_sdk_ts`
- Generator: `@hey-api/openapi-ts`
- Client style: generated fetch client

## Python

- Distribution package name: `nova-sdk-py`
- Import package name: `nova_sdk_py`
- Source package directory: `packages/nova_sdk_py`
- Generator: `openapi-python-client`
- Output rule: thin templates/config, no huge patch step

## R

- Canonical source package directory: `packages/nova_sdk_r`
- Published R package name: `nova`
- Exported surface: `create_nova_client()`, `nova_bearer_token()`, and `nova_<operation_id>()`
- Strategy: thin `httr2` wrapper package
- No OpenAPI Generator R output in the canonical repo

## Shared principles

- one client package per language
- one auth model across all clients
- typed models generated where it materially reduces maintenance
- handwritten code only where generators are weaker than the language-native ecosystem
