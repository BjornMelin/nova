---
Spec: 0019
Title: Auth execution and threadpool safety contract
Status: Active
Version: 2.1
Date: 2026-03-05
Related:
  - "[ADR-0026: Fail-fast runtime configuration and safe auth execution](../adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)"
  - "[ADR-0004: Adopt oidc-jwt-verifier as the canonical JWT/OIDC verification engine](../adr/ADR-0004-canonical-oidc-jwt-verifier-adoption.md)"
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
  - "[SPEC-0018: Runtime configuration and startup validation contract](./SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
---

## 1. Scope

Defines how Nova executes local and remote auth paths safely in async runtime
code.

## 2. Canonical auth execution rules

1. Local synchronous JWT verification must run behind a threadpool boundary.
2. Remote auth remains optional; when enabled it fails closed.
3. Remote auth HTTP calls must reuse a process-scoped async client rather than
   creating a new client per request-path invocation.
4. Process-scoped remote auth clients must be closed during application
   shutdown.
5. Auth failure responses preserve the canonical Nova/Auth API contract,
   including RFC 6750 challenge behavior on `401` responses.
6. Presigned URLs, bearer tokens, and signed query values must never be logged.

## 3. Threadpool and limiter contract

1. `OIDC_VERIFIER_THREAD_TOKENS` governs verifier concurrency only.
2. Generic blocking I/O offloads must use a separate limiter contract and must
   not silently share verifier-specific capacity decisions.
3. Runtime code must not rely on unbounded synchronous work in async request
   handlers.
4. Process-wide limiter mutation is not the general-purpose concurrency control
   strategy for the runtime.

## 4. Package-specific contract

1. `nova_auth_api` owns principal mapping and token verify/introspect semantics.
2. `nova_file_api` may call local verification or remote auth, but it must use
   the same canonical auth semantics and safe thread boundaries.
3. `nova_dash_bridge` may forward auth context and call canonical Nova
   contracts through `nova_file_api.public`, but it must not create divergent
   verification behavior.

## 5. Acceptance criteria

1. Active runtime docs identify auth execution safety as runtime authority, not
   CI/CD IAM authority.
2. Readiness and startup docs do not weaken fail-closed auth behavior.
3. Runtime safety docs explicitly distinguish verifier concurrency from other
   blocking work.
4. Remote auth lifecycle docs require a single scoped async client plus
   explicit shutdown cleanup.

## 6. Traceability

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [NFR-0000](../requirements.md#nfr-0000-security-baseline)
- [NFR-0001](../requirements.md#nfr-0001-performance-and-event-loop-safety)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)
