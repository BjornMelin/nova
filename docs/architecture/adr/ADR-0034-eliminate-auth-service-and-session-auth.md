# ADR-0034 — Eliminate auth service and session auth

> **Implementation state:** Approved target-state ADR. The current codebase still carries legacy auth-service and session-style seams; this ADR defines their removal.


## Status
Accepted

## Decision

Use **bearer JWT only** for all public API access. Verify JWTs in-process in the main API with an async verifier. Delete the dedicated auth service and all auth SDK packages.

## Context

The attached repo still carries three auth modes and a dedicated auth microservice, plus session-style public auth semantics that complicate clients, OpenAPI, and platform topology.

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

- delete `packages/nova_auth_api`
- delete `packages/nova_sdk_auth`
- delete `packages/nova_sdk_py_auth`
- delete `packages/nova_sdk_r_auth`
- remove `JWT_REMOTE`, `SAME_ORIGIN`, `X-Session-Id`, body `session_id`, and `X-Scope-Id`
