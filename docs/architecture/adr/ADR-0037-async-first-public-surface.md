---
ADR: 0037
Title: Green-field async-first public surface
Status: Accepted
Version: 1.0
Date: 2026-03-19
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](../spec/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0041: Green-field shared pure ASGI middleware and errors](./ADR-0041-shared-pure-asgi-middleware-and-errors.md)"
  - "[SPEC-0027: Public HTTP contract revision and bearer auth](../spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md)"
  - "[ADR-0026: Fail-fast runtime configuration and safe auth execution](./ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)"
  - "[SPEC-0019: Auth execution and threadpool safety contract](../spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md)"
  - "[Green-field simplification program](../../plan/greenfield-simplification-program.md)"
References:
  - "[Green-field evidence (Framework A)](../../plan/greenfield-evidence/DECISION_FRAMEWORKS_AND_SCORES.md)"
---

## Summary

The canonical **`nova_file_api.public`** surface is **async-first**; FastAPI
routes call it directly. Sync wrappers remain only at **true** sync-only edges
(for example some Dash/Flask adapters). Winning option: **9.35/10** (Framework
A).

## Context

- The transfer core is async-native; sync façades over async internals add
  thread-pool churn.
- When JWT verification becomes async-native in-process ([ADR-0033](./ADR-0033-single-runtime-auth-authority.md)),
  [ADR-0026](./ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)
  / [SPEC-0019](../spec/SPEC-0019-auth-execution-and-threadpool-safety-contract.md)
  apply to **remaining** sync work only (not to async-safe JWT on the event
  loop).
- Execution order: program branch 6.

## Alternatives

- **A:** Keep sync façade over async core.
- **B:** Async-first canonical surface + thin sync adapters.
- **C:** Sync-first canonical surface.

## Decision framework (Framework A)

| Option | Native dependency leverage | Entropy / LOC / file reduction | Reliability / performance | Security / operability | DX / maintainability | Implementation tractability | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A: Keep sync façade over async core | 4 | 3 | 6 | 7 | 5 | 8 | 5.00 |
| **B: Async-first canonical surface + thin sync adapters** | **10** | **9** | **9** | **9** | **10** | **8** | **9.35** |
| C: Sync-first canonical surface | 3 | 4 | 4 | 6 | 5 | 7 | 4.35 |

## Decision

**Option B** is accepted.

Implementation commitments:

- Convert or expose public entrypoints as async-first APIs consumed by FastAPI.
- Keep sync adapters minimal and documented for sync-bound consumers only.
- Branch `refactor/public-async-first-surface`.

## Related requirements

- [GFR-R3](../requirements.md#gfr-r3--async-correctness-is-mandatory)
- [GFR-R6](../requirements.md#gfr-r6--sdks-must-feel-native-per-language)

## Consequences

1. **Positive:** Clearer stack, less hidden blocking, better fit with FastAPI.
2. **Trade-offs:** Breaking change for consumers that depended on sync-first
   public APIs.
3. **Ongoing:** Bridge packages (for example Dash) stay explicitly supported at
   the edge.

## Changelog

- 2026-03-19: Canonical ADR ported from green-field pack ADR-0005 (async-first);
  cross-links ADR-0026/SPEC-0019 for threadpool scope.
