# SPEC-0030 -- SDK generation and package layout

> **Implementation state:** Implemented in the current repository baseline as the active SDK generation and package layout contract.

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
