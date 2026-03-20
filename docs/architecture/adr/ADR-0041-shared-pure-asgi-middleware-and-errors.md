---
ADR: 0041
Title: Green-field shared pure ASGI middleware and errors
Status: Accepted
Version: 1.0
Date: 2026-03-19
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](../spec/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0036: Green-field native FastAPI OpenAPI contract expression](./ADR-0036-native-fastapi-openapi-contract.md)"
  - "[ADR-0037: Green-field async-first public surface](./ADR-0037-async-first-public-surface.md)"
  - "[Green-field simplification program](../../plan/greenfield-simplification-program.md)"
References:
  - "[Green-field evidence (Framework A)](../../plan/greenfield-evidence/DECISION_FRAMEWORKS_AND_SCORES.md)"
  - "[Change impact map](../../plan/greenfield-evidence/CHANGE_IMPACT_MAP.md)"
---

## Summary

Request context propagation and shared **error envelope** behavior move to **one**
shared **pure ASGI** middleware layer plus shared exception-registration
primitives, replacing duplicated service-local HTTP middleware. Winning option:
**9.15/10** (Framework A).

## Context

- Per-service middleware and ad-hoc error glue duplicated logic and hit
  limitations of higher-level HTTP middleware patterns.
- Execution order: program branch 5 (after native OpenAPI branch 4 in the
  program graph).

## Alternatives

- **A:** Service-local HTTP middleware duplication.
- **B:** Shared pure ASGI middleware + shared error registration.
- **C:** Per-route request context and manual error wrapping.

## Decision framework (Framework A)

| Option | Native dependency leverage | Entropy / LOC / file reduction | Reliability / performance | Security / operability | DX / maintainability | Implementation tractability | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A: Service-local HTTP middleware duplication | 3 | 2 | 6 | 6 | 4 | 8 | 4.25 |
| **B: Shared pure ASGI middleware + shared error registration** | **10** | **8** | **9** | **9** | **10** | **8** | **9.15** |
| C: Per-route request context and manual error wrapping | 4 | 3 | 5 | 5 | 3 | 6 | 4.10 |

## Decision

**Option B** is accepted.

Implementation commitments:

- Implement shared request-context / correlation-id behavior as pure ASGI
  middleware in `nova_runtime_support` (or agreed shared package), not
  per-service copies.
- Centralize error registration and response envelope consistency with shared
  primitives.
- Delete duplicate middleware modules in service packages after migration.
- Branch `refactor/runtime-pure-asgi-middleware-errors`.

## Related requirements

- [GFR-R9](../requirements.md#gfr-r9--deterministic-build-and-verification)
- [GFR-R10](../requirements.md#gfr-r10--repo-should-shrink-after-every-accepted-branch)

## Consequences

1. **Positive:** One place to fix middleware bugs; consistent observability
   fields; less code.
2. **Trade-offs:** Touches shared boot paths; regression-test error JSON and
   headers carefully.
3. **Ongoing:** Align tests and docs that assert request-id and error shapes.

## Changelog

- 2026-03-19: Canonical ADR ported from green-field pack ADR-0009.
