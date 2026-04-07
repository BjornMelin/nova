---
Spec: 0019
Title: Auth execution and threadpool safety contract
Status: Active
Version: 2.4
Date: 2026-04-06
Related:
  - "[ADR-0026: Fail-fast runtime configuration and safe auth execution](../adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)"
  - "[ADR-0004: Adopt oidc-jwt-verifier as the canonical JWT/OIDC verification engine](../adr/ADR-0004-canonical-oidc-jwt-verifier-adoption.md)"
  - "[SPEC-0006: JWT/OIDC verification and principal mapping](./SPEC-0006-jwt-oidc-verification-and-principal-mapping.md)"
  - "[SPEC-0018: Runtime configuration and startup validation contract](./SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
---

## 1. Scope

Defines how Nova executes in-process auth safely in async runtime code.

## 2. Canonical auth execution rules

1. Local synchronous JWT verification must run behind a threadpool boundary
   **when** verification remains synchronous on async request paths. When JWT
   verification is async-native in the file API, the process-scoped async
   verifier must be instantiated during managed runtime
   bootstrap for the active app surface: the Lambda path bootstraps one
   process-reused `ApiRuntime` container before Mangum request handling, and
   local development uses the managed FastAPI app builder. The verifier must
   be explicitly closed with an awaited `aclose()` during managed shutdown; do
   not rely on background tasks, implicit destructors, or ad-hoc per-request
   creation.
2. The canonical readiness probe for bearer-token auth delegates to the same
   process-scoped async verifier through its public verifier-owned JWKS
   lifecycle/readiness APIs; Nova must not maintain a second private JWKS
   readiness path.
3. Dedicated auth microservice HTTP calls are not part of the target
   architecture (superseded `ADR-0005` / `SPEC-0007`).
4. Auth failure responses preserve the canonical Nova bearer-auth contract,
   including RFC 6750 challenge behavior on `401` responses.
5. Presigned URLs, bearer tokens, and signed query values must never be logged.
   When auth verification is async-native, the verifier lifecycle requirement
   above applies to the same process-scoped verifier that handles those
   values, so the verifier must still be created during managed runtime
   bootstrap and closed with awaited `aclose()` on shutdown.

## 3. Threadpool and limiter contract

1. Generic blocking I/O offloads must use explicit limiter boundaries when
   needed and must not silently share verifier-specific capacity decisions.
2. Runtime code must not rely on unbounded synchronous work in async request
   handlers.
3. Process-wide limiter mutation is not the general-purpose concurrency control
   strategy for the runtime.
4. Active runtime docs and settings must not expose a generic blocking-I/O
   thread-token tuning surface when no such runtime setting exists.
5. The bridge package must not reintroduce server-side sync-over-async transfer
   adapters. Embedded FastAPI/Flask transfer surfaces are retired; browser
   helpers forward bearer auth to the canonical Nova HTTP API instead.

## 4. Package-specific contract

1. `nova_file_api` owns in-process JWT verification, principal mapping, and
   authorization semantics.
2. `nova_dash_bridge` may forward auth context into canonical Nova HTTP
   requests, but it must not create divergent verification behavior.
3. `nova_dash_bridge` must not expose bridge-local threadpool token tuning as a
   transfer-surface config contract.

## 5. Acceptance criteria

1. Active runtime docs identify auth execution safety as runtime authority, not
   CI/CD IAM authority.
2. Readiness and startup docs do not weaken fail-closed auth behavior.
3. Runtime safety docs explicitly distinguish async-native verification from
   any remaining blocking work.
4. Active docs describe bearer-only browser/Dash forwarding and do not
   reintroduce bridge-owned server adapters.

## 6. Traceability

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [NFR-0000](../requirements.md#nfr-0000-security-baseline)
- [NFR-0001](../requirements.md#nfr-0001-performance-and-event-loop-safety)
