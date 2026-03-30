---
Spec: 0001
Title: Security Model
Status: Active
Version: 1.7
Date: 2026-03-20
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](./superseded/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0004: Canonical OIDC verifier adoption](../adr/ADR-0004-canonical-oidc-jwt-verifier-adoption.md)"
  - "[ADR-0033: Green-field single runtime auth authority](../adr/ADR-0033-single-runtime-auth-authority.md)"
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
References:
  - "[S3 presigned URL overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)"
  - "[AWS presigned URL best practices](https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/introduction.html)"
  - "[Starlette thread pool behavior](https://www.starlette.io/threadpool/)"
  - "[AnyIO threads guidance](https://anyio.readthedocs.io/en/latest/threads.html)"
  - "[RFC 6750 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)"
  - "[RFC 8725 JWT Best Current Practices](https://datatracker.ietf.org/doc/html/rfc8725)"
---

## 1. Authentication model

### 1.1 Public bearer-JWT mode

The public runtime contract uses bearer JWT authentication only. Verification
uses canonical `oidc-jwt-verifier` policy, and caller scope/tenancy are derived
from verified claims rather than from request bodies or custom scope headers.

Public requests MUST send `Authorization: Bearer <token>`.

- Missing or invalid bearer tokens MUST return `401`.
- Authorization failures after token verification MUST return `403`.
- `401` responses MUST include RFC 6750-compatible `WWW-Authenticate` headers.
- `session_id`, `X-Session-Id`, and `X-Scope-Id` are not part of the active
  public contract and MUST NOT be used as authorization inputs.

### 1.2 Remote auth hard cut

There is no optional remote auth mode in the active runtime architecture. JWT
verification happens inside `nova_file_api`, and deploy/release contracts MUST
not reference `nova-auth-api` or remote-auth runtime configuration.

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

Client `session_id` MUST NOT override trusted JWT identity.

## 5. Sensitive data protections

- Bearer tokens and authorization headers MUST NOT be logged.
- Presigned URLs and query signatures MUST NOT be logged.
- Error payloads MUST NOT include sensitive authentication or URL material.

## 6. Worker result persistence boundary

- Worker status updates MUST execute through shared runtime services or direct
  persistence primitives inside Nova; there is no internal HTTP callback route.
- Worker result writes MUST keep terminal-state immutability and same-state
  idempotency rules from the job lifecycle contract.
- Worker configuration MUST not introduce shared-secret callback credentials for
  result updates.

## 7. Traceability

- [FR-0003](../requirements.md#fr-0003-key-generation-and-scope-enforcement)
- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [NFR-0000](../requirements.md#nfr-0000-security-baseline)
- [NFR-0001](../requirements.md#nfr-0001-performance-and-event-loop-safety)
