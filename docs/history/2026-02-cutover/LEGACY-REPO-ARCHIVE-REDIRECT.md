# Legacy Repository Archive and Redirect Guide (Historical)

Status: Historical record
Date: 2026-02-12

## Objective

Archive legacy runtime repositories and redirect consumers to
`nova` monorepo packages and paths.

## Legacy Repository Scope

- Former bridge runtime repository (retired)

## Redirect Targets

- Runtime and API contract source:
  `nova` runtime monorepo
- Bridge package:
  `packages/nova_dash_bridge`
- Core transfer runtime package:
  `packages/nova_file_api`
- Auth runtime package:
  `packages/nova_auth_api`

## Local Actions Completed

- [x] Added archive redirect notice files in legacy repo.
- [x] Updated legacy README with migration destination and path guidance.
- [x] Confirmed canonical endpoint contract usage:
  - `/api/transfers/*`
  - `/api/jobs/*`

## Disposition

- Historical operations complete.
- Repository is no longer part of active runtime documentation.

## Consumer Migration Summary

- Use canonical imports:
  - `nova_dash_bridge`
  - `nova_file_api`
- Use canonical route calls:
  - `/api/transfers/*`
  - `/api/jobs/*`
