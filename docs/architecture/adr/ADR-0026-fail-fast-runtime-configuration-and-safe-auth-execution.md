---
ADR: 0026
Title: Fail-fast runtime configuration and safe auth execution
Status: Accepted
Version: 2.1
Date: 2026-03-05
Related:
  - "[ADR-0024: Layered runtime authority pack for the Nova monorepo](./ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0025: Runtime monorepo component boundaries and ownership](./ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md)"
  - "[SPEC-0018: Runtime configuration and startup validation contract](../spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[SPEC-0019: Auth execution and threadpool safety contract](../spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](./ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
---

## Summary

Nova runtime fails fast on invalid configuration, exposes explicit readiness
checks for the dependencies it currently evaluates, and executes synchronous
token verification only behind explicit threadpool boundaries. Runtime safety
is not delegated to deploy-automation IAM docs.

## Context

Nova exposes configuration-heavy runtime behavior:

- queue backend selection
- activity-store backend selection
- same-origin, local OIDC, and remote auth modes
- worker callback/update-token behavior
- readiness and health semantics

Drift created two failure modes:

1. invalid backend combinations surviving until first request, and
2. synchronous JWT verification sharing ambient AnyIO limits with unrelated
   blocking work.

The active runtime safety ADR must define the target-state rules directly.

## Alternatives and scored decision

### Criteria and weights

- Solution leverage: 35%
- Application value: 30%
- Maintenance and cognitive load: 25%
- Architectural adaptability: 10%

### Option scores

| Option | Weighted score (/10) |
| --- | ---: |
| A. Allow lazy runtime misconfiguration discovery and rely on default process-wide threadpool behavior | 5.8 |
| B. Enforce typed fail-fast settings, startup validation, explicit readiness checks, and auth threadpool boundaries | **9.7** |
| C. Move all auth verification to a required remote service and keep runtime config permissive | 7.1 |

Threshold policy: only options `>= 9.0` are accepted.

## Decision

Choose **Option B**.

### Required characteristics

1. Runtime settings are typed and environment-driven.
2. Backend couplings fail at startup, not during live request handling.
3. `/v1/health/ready` reports the current runtime dependency checks
   explicitly.
4. Cache and activity-store degradation remain visible in readiness
   diagnostics; overall readiness follows the active check set until finer
   dependency scoping is implemented.
5. Local synchronous OIDC/JWT verification never runs directly on async
   event-loop paths.
6. `OIDC_VERIFIER_THREAD_TOKENS` is verifier-only authority; generic blocking
   I/O uses a separate limiter contract.
7. Remote auth remains optional, fail-closed when enabled, and reuses a
   process-scoped async HTTP client with explicit shutdown cleanup.
8. Deploy and operator docs must not claim an `IDEMPOTENCY_MODE` contract or
   fail-closed shared-cache semantics before the runtime implements them.

## Consequences

### Positive

- Runtime failures surface during boot or readiness instead of mid-request.
- Auth safety rules stay close to the code paths they govern.
- Operational docs can distinguish critical readiness gates from observability
  signals.

### Trade-offs

- Startup becomes stricter and rejects more partial configurations.
- Thread-limiter settings become explicit operational inputs instead of hidden
  defaults.

## Explicit non-decisions

- No ambient mutation of the process-wide AnyIO limiter as a general runtime
  concurrency strategy.
- No readiness model driven by optional feature flags or non-critical observers.
- No deploy-automation IAM document as substitute authority for runtime auth
  execution rules.

## Changelog

- 2026-03-05: Restored `ADR-0026` to runtime configuration and auth-safety
  governance and moved CI/CD IAM partitioning to `ADR-0032`.
- 2026-03-05: Added process-scoped remote-auth client lifecycle requirements.
- 2026-03-14: Reconciled active docs to the current aggregate readiness
  contract and removed premature `IDEMPOTENCY_MODE` claims from the active
  runtime authority pack.
