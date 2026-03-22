---
Spec: 0027
Title: Public HTTP contract revision and bearer auth
Status: Active
Version: 1.0
Date: 2026-03-19
Supersedes: "[SPEC-0007: Auth API contract (superseded)](./superseded/SPEC-0007-auth-api-contract.md)"
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[ADR-0033: Green-field single runtime auth authority](../adr/ADR-0033-single-runtime-auth-authority.md)"
  - "[ADR-0034: Green-field bearer JWT public auth contract](../adr/ADR-0034-bearer-jwt-public-auth-contract.md)"
  - "[ADR-0036: Green-field native FastAPI OpenAPI contract expression](../adr/ADR-0036-native-fastapi-openapi-contract.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
  - "[SPEC-0016: v1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
---

## 1. Purpose

Define the **target** public HTTP contract for auth, request/response shape
expectations, error schema, and OpenAPI obligations for the Nova file API
runtime.

## 2. Path namespace vs contract revision

- **URL namespace** remains canonical **`/v1/*`** plus **`/metrics/summary`**
  per [ADR-0023](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md) and
  [SPEC-0016](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md).
- This specification’s “revision” refers to **auth model, headers, and OpenAPI
  expression**, not a new `/v2/*` prefix unless explicitly introduced by a future
  ADR.

There is **no** separate `nova-auth-api` HTTP surface; token verification and
introspection routes described in superseded
[SPEC-0007](./superseded/SPEC-0007-auth-api-contract.md) are **retired**.

## 3. Auth

- Public callers authenticate with **bearer JWT** only.
- Scope, tenant, permissions, and subject are derived from **verified claims**
  in the file API runtime ([ADR-0034](../adr/ADR-0034-bearer-jwt-public-auth-contract.md)).
- `session_id`, `X-Session-Id`, and `X-Scope-Id` are **not** part of the public
  contract for authorization scope binding.
- OpenAPI documents bearer auth using FastAPI **security dependencies** so the
  emitted document matches runtime behavior ([ADR-0036](../adr/ADR-0036-native-fastapi-openapi-contract.md)).

## 4. Requests

- Request bodies contain **domain data only**; no body field exists solely to
  carry auth/session scope.
- Request and response models are typed and explicit.

## 5. Responses

- Route declarations use typed return values or `response_model` where
  applicable.
- Non-2xx responses are declared with native FastAPI `responses=` where
  appropriate.
- Error envelopes are consistent across the public API and include
  correlation / request IDs (shared ASGI layer per
  [ADR-0041](../adr/ADR-0041-shared-pure-asgi-middleware-and-errors.md)).

## 6. OpenAPI

- The public OpenAPI document is generated from runtime code; runtime remains
  the contract source ([ADR-0002](../adr/ADR-0002-openapi-as-contract-and-sdk-generation.md)).
- Bearer auth is emitted through FastAPI security dependencies, and public
  non-2xx responses are declared directly through route or router `responses=`
  metadata.
- `operationId` values remain stable and SDK-friendly through explicit route
  `operation_id=` declarations.

## 7. Breaking changes explicitly accepted (green-field program)

- Removal of same-origin public auth mode that depended on session/header
  surrogates.
- Removal of `session_id` from public request models for scope binding.
- Removal of dedicated auth service HTTP routes and auth-only SDK families.

## 8. Traceability

- [GFR-R2](../requirements.md#gfr-r2--auth-context-comes-from-verified-claims)
- [GFR-R4](../requirements.md#gfr-r4--public-contract-must-be-explicit)
- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)

## Changelog

- 2026-03-19: Initial canonical SPEC; supersedes SPEC-0007; ports green-field
  pack SPEC-0001 intent with explicit `/v1/*` namespace clarification.
