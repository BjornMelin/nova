---
Spec: 0006
Title: JWT/OIDC Verification and Principal Mapping
Status: Active
Version: 1.0
Date: 2026-02-12
Related:
  - "[SPEC-0001: Security model](./SPEC-0001-security-model.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0007: Auth API contract](./SPEC-0007-auth-api-contract.md)"
  - "[ADR-0004: Canonical OIDC verifier adoption](../adr/ADR-0004-canonical-oidc-jwt-verifier-adoption.md)"
References:
  - "[oidc-jwt-verifier source](https://github.com/BjornMelin/oidc-jwt-verifier)"
  - "[RFC 8725 JWT Best Current Practices](https://datatracker.ietf.org/doc/html/rfc8725)"
  - "[RFC 6750 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)"
  - "[Auth0 validate access tokens](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens)"
---

## 1. Canonical verification engine

The service MUST use `oidc-jwt-verifier` as the canonical JWT/OIDC verification engine in JWT mode.

The service MUST NOT implement custom duplicate JWT cryptographic verification logic unless introduced by a future ADR.

## 2. Configuration model

JWT mode configuration MUST support generic OIDC inputs:

- `OIDC_ISSUER`
- `OIDC_AUDIENCE` (single or list)
- `OIDC_JWKS_URL`

Optional provider presets MAY map provider-specific env vars (for example Auth0 domain-based settings) to these canonical fields.

## 3. Async integration rule

`oidc-jwt-verifier` verification is synchronous.

In FastAPI async dependencies, verification MUST run through a threadpool boundary (`anyio.to_thread.run_sync` or equivalent) to prevent event-loop blocking.

## 4. Principal mapping contract

A normalized principal object MUST be derived from verified claims with at least:

- `subject`
- `scopes`
- `permissions`
- `tenant_id` or `org_id` when available
- `raw_claims` (sanitized in logs)

`scope_id` derivation priority:

1. explicit trusted tenant/org claim (if configured)
2. `sub`
3. session-derived fallback only in non-JWT mode

Client-provided `session_id` MUST NOT override trusted JWT-derived scope identity.

## 5. Authorization behavior

Authorization checks MUST enforce:

- key-prefix scope ownership
- multipart continuation ownership for `key` + `upload_id`
- required scope/permission policy where configured

Failures MUST map to stable error envelopes and include `request_id`.

## 6. Error mapping

JWT verification/authz failures MUST map to API domain codes consistently:

- `missing_token`
- `invalid_token`
- `token_expired`
- `invalid_issuer`
- `invalid_audience`
- `insufficient_scope`
- `insufficient_permissions`

401 responses SHOULD include RFC 6750-compatible `WWW-Authenticate` headers.

## 7. Security constraints

The verifier path MUST reject dangerous header parameters (`jku`, `x5u`, `crit`) and disallowed algorithms.

Tokens and presigned URL query strings MUST never be emitted to logs.

## 8. Test requirements

Minimum tests MUST include:

- valid token acceptance
- signature/issuer/audience/expiry failures
- missing/invalid kid and JWKS key miss behavior
- scope and permission authorization failures
- async dependency threadpool boundary behavior

## 9. Traceability

- [FR-0004](../requirements.md#fr-0004-auth-and-authorization-pluggable)
- [FR-FT-006](../requirements.md#fr-ft-006-auth-and-authorization-behavior)
- [NFR-0000](../requirements.md#nfr-0000-observability)
- [NFR-FT-001](../requirements.md#nfr-ft-001-security-baseline)
