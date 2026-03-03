---
Spec: 0001
Title: Security Model
Status: Active
Version: 1.6
Date: 2026-03-03
Related:
  - "[ADR-0004: Canonical OIDC verifier adoption](../adr/ADR-0004-canonical-oidc-jwt-verifier-adoption.md)"
  - "[ADR-0005: Dedicated nova-auth-api track](../adr/ADR-0005-add-dedicated-nova-auth-api-service.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
References:
  - "[S3 presigned URL overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)"
  - "[AWS presigned URL best practices](https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/introduction.html)"
  - "[Starlette thread pool behavior](https://www.starlette.io/threadpool/)"
  - "[AnyIO threads guidance](https://anyio.readthedocs.io/en/latest/threads.html)"
  - "[RFC 6750 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)"
  - "[RFC 8725 JWT Best Current Practices](https://datatracker.ietf.org/doc/html/rfc8725)"
---

## 1. Authentication modes

### 1.1 Same-origin mode

Primary deployment model. Upstream application identity is trusted and mapped to
scope.

For body-less scope-bound routes (for example `GET /v1/jobs/{job_id}`), caller
scope MUST be conveyed using trusted headers (`X-Scope-Id` or
`X-Session-Id`).
When both headers are present, `X-Session-Id` MUST win for scope binding.
When `X-Session-Id` and body `session_id` differ, request validation MUST fail
with `422` and message `conflicting session scope`.
When `X-Session-Id` is absent and `X-Scope-Id` plus body `session_id` differ,
authentication MUST fail with `401` and message `conflicting session scope`.

### 1.2 Local JWT/OIDC verification mode

Default token mode. Verification uses canonical `oidc-jwt-verifier` policy.

### 1.3 Optional remote auth mode

Uses `nova-auth-api` over HTTP. This mode MUST be explicit and fail-closed on
connectivity or non-success auth responses.

## 2. JWT verification and async safety

- Enforce issuer, audience, expiry, and not-before checks.
- Enforce strict algorithm allowlist.
- Reject dangerous JWT header parameters (`jku`, `x5u`, `crit`).
- Synchronous verifier calls in async dependencies MUST run via threadpool
  boundary (`anyio.to_thread.run_sync` or equivalent).
- When verification fails and a `401` is returned, implementations MUST include
  `WWW-Authenticate` per RFC 6750 and preserve verifier semantics from
  `AuthError.www_authenticate_header()` (including token error fields).

## 3. Authorization rules

- Every key operation MUST enforce caller scope ownership.
- Prefix checks MUST limit access to approved upload/export/tmp prefixes.
- Multipart continuation MUST enforce key ownership for the same caller scope.

## 4. Scope derivation

Scope derivation priority:

1. trusted tenant/org claim
2. trusted subject claim
3. session fallback only in non-JWT mode

Client `session_id` MUST NOT override trusted JWT identity.

## 5. Sensitive data protections

- Bearer tokens and authorization headers MUST NOT be logged.
- Presigned URLs and query signatures MUST NOT be logged.
- Error payloads MUST NOT include sensitive authentication or URL material.

## 6. Worker callback authentication

- Internal worker status updates
  (`POST /v1/internal/jobs/{job_id}/result`)
  MUST use a shared-secret header validation pattern (`X-Worker-Token`) when a
  worker token is configured.
- Invalid worker token values MUST return `403`.
- Worker tokens MUST be delivered via environment/secret configuration, never
  hardcoded in source.

## 7. Traceability

- [FR-0003](../requirements.md#fr-0003-key-generation-and-scope-enforcement)
- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [NFR-0000](../requirements.md#nfr-0000-security-baseline)
- [NFR-0001](../requirements.md#nfr-0001-performance-and-event-loop-safety)
