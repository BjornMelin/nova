# Canonical client package layout

## TypeScript

- Package name: `@nova/sdk`
- Source package directory: `packages/nova_sdk_ts`
- Generator: `@hey-api/openapi-ts`
- Compiler baseline: `typescript@5.9.3`
- Client style: generated fetch client
- Public imports:
  - `@nova/sdk/client`
  - `@nova/sdk/sdk`
  - `@nova/sdk/types`
- Internal generated scaffold files may exist under the bundled client tree;
  they are not public API.

## Python

- Package name: `nova-sdk-py` (or `nova_sdk_py` import package)
- Source package directory: `packages/nova_sdk_py`
- Generator: `openapi-python-client`
- Output rule: thin templates/config, no huge patch step

## R

- Package name: `nova`
- Source package directory: `packages/nova_sdk_r`
- Strategy: thin `httr2` wrapper package
- No OpenAPI Generator R output in the canonical repo

## Shared principles

- one client package per language
- one committed reduced public OpenAPI artifact for TS/Python/R generation:
  `packages/contracts/openapi/nova-file-api.public.openapi.json`
- one auth model across all clients
- typed models generated where it materially reduces maintenance
- handwritten code only where generators are weaker than the language-native ecosystem
