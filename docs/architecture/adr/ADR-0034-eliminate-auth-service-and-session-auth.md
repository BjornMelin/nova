# ADR-0034 -- Eliminate auth service and session auth

> **Implementation state:** Implemented in the current repository baseline, with only legacy references/assets still requiring retirement.

## Status
Accepted

## Decision

Use **bearer JWT only** for all public API access. Verify JWTs in-process in
the main API with an async verifier. Keep the dedicated auth service and auth
SDK packages removed from the active public surface.

## Context

The current repository has already moved the active public contract to bearer
JWT only, but legacy references and superseded artifacts still need to stay
out of active docs and operator paths.

## Why this wins

- one auth model for all clients
- one fewer deployable service
- one fewer network hop on authenticated requests
- cleaner OpenAPI and SDK generation
- fail-closed security with fewer moving parts

## Rejected options

- remote auth verification service
- hybrid same-origin/session plus JWT
- maintaining auth-specific SDK packages

## Consequences

- keep `packages/nova_auth_api` and auth-specific SDK packages out of the
  active package/runtime contract
- keep `JWT_REMOTE`, `SAME_ORIGIN`, `X-Session-Id`, body `session_id`, and
  `X-Scope-Id` out of the public auth contract and active docs
