---
ADR: 0026
Title: Fail-fast runtime configuration and safe auth execution
Status: Accepted
Version: 2.4
Date: 2026-03-20
Related:
  - "[ADR-0023](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000](../spec/superseded/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0024: Layered runtime authority pack for the Nova monorepo](./ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0025: Runtime monorepo component boundaries and ownership](./ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md)"
  - "[SPEC-0018: Runtime configuration and startup validation contract](../spec/SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[SPEC-0019: Auth execution and threadpool safety contract](../spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](./ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
---

## Summary

Nova runtime fails fast on invalid configuration, exposes explicit readiness
checks for the dependencies it currently evaluates, and keeps any remaining
synchronous token verification behind explicit threadpool boundaries while the
public file API uses async-native verification. Runtime safety is not delegated
to deploy-automation IAM docs.

## Context

Nova exposes configuration-heavy runtime behavior:

- queue backend selection
- activity-store backend selection
- local OIDC bearer-JWT auth mode
- worker callback/update-token behavior
- readiness and health semantics

Drift created two failure modes:

1. invalid backend combinations surviving until first request, and
2. synchronous JWT verification sharing ambient AnyIO limits with unrelated
   blocking work.

The active runtime safety ADR must define the current-state rules directly.

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
   diagnostics; overall readiness gates only traffic-critical dependencies
   derived from the active runtime settings.
5. Local synchronous OIDC/JWT verification never runs directly on async
   event-loop paths.
6. Any remaining threadpool/offload tuning stays scoped to blocking work that
   still exists outside the async-native JWT path.
7. Deploy and operator docs must enforce the current strict idempotency
   contract: `IDEMPOTENCY_ENABLED=true` requires the shared DynamoDB
   idempotency table, and shared-store failures fail closed without an
   `IDEMPOTENCY_MODE` surface.
8. Deploy scripts, infra tests, and operator docs consume a generated
   runtime-config contract artifact derived from the typed runtime settings plus
   the minimal curated deploy metadata required for the active Lambda/runtime
   deploy wiring.
9. Runtime settings declare explicit string `validation_alias` values for env
   names, and release tooling reads `validation_alias` only.

## Consequences

### Positive

- Runtime failures surface during boot or readiness instead of mid-request.
- Auth safety rules stay close to the code paths they govern.
- Operational docs can distinguish critical readiness gates from observability
  signals.
- Runtime deploy/config drift is checked as generated-artifact freshness rather
  than by maintaining duplicate handwritten env matrices.

### Trade-offs

- Startup becomes stricter and rejects more partial configurations.
- Remaining blocking-work boundaries stay explicit instead of relying on hidden
  defaults.

## Explicit non-decisions

- No ambient mutation of the process-wide AnyIO limiter as a general runtime
  concurrency strategy.
- No readiness model driven by optional feature flags or non-critical observers.
- No deploy-automation IAM document as substitute authority for runtime auth
  execution rules.

## Green-field program supplement

With the active async-native verifier and explicit runtime bootstrap now in
place, FastAPI auth paths have reduced the amount of work that must use
threadpool offload. This ADR and
[SPEC-0019](../spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md)
continue to govern **any remaining** synchronous verification or blocking work
on async handlers until and unless fully eliminated.

## Changelog

- 2026-03-05: Restored `ADR-0026` to runtime configuration and auth-safety
  governance and moved CI/CD IAM partitioning to `ADR-0032`.
- 2026-03-05: Added process-scoped remote-auth client lifecycle requirements.
- 2026-03-14: Updated readiness-contract language and removed premature
  `IDEMPOTENCY_MODE` claims from the active runtime authority pack.
- 2026-03-16: Finalized strict shared idempotency and dependency-scoped
  readiness gating in the active runtime contract.
- 2026-03-17: Added the generated runtime-config contract artifact as the
  required deploy/docs/test anti-drift mechanism.
- 2026-03-19: Updated the ADR for the async-native in-process verifier and the
  retired remote-auth path.
- 2026-03-25: Tightened the runtime-config contract to require explicit string
  `validation_alias` mappings and removed implicit env-name derivation from the
  release tooling path.
