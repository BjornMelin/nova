---
ADR: 0036
Title: Green-field native FastAPI OpenAPI contract expression
Status: Superseded
Version: 1.0
Date: 2026-03-19
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](../../spec/superseded/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0041: Green-field shared pure ASGI middleware and errors](./ADR-0041-shared-pure-asgi-middleware-and-errors.md)"
  - "[SPEC-0027: Public HTTP contract revision and bearer auth](../spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md)"
  - "[ADR-0002: OpenAPI as contract and SDK generation](./ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[Green-field simplification program](../../plan/greenfield-simplification-program.md)"
References:
  - "[Green-field evidence (Framework A)](../../plan/greenfield-evidence/DECISION_FRAMEWORKS_AND_SCORES.md)"
  - "[Rejected and deferred options](../../plan/greenfield-evidence/REJECTED_AND_DEFERRED_OPTIONS.md)"
---

## Summary

OpenAPI and operation identity come primarily from **native FastAPI**
declarations (`responses=`, models, security dependencies, explicit
`operation_id`, router metadata). Hand-authored static OpenAPI as the source of
truth is out of scope. Winning option: **9.10/10** (Framework A).

## Context

- Nova historically patched generated OpenAPI heavily after FastAPI emission.
- Stable `operationId` values and SDK generation still matter.
- [ADR-0002](./ADR-0002-openapi-as-contract-and-sdk-generation.md) remains the
  umbrella “OpenAPI is contract” decision; this ADR narrows **how** the schema
  is produced.
- Execution order: program branch 4.

## Alternatives

- **A:** Keep bespoke schema surgery and path/method registries.
- **B:** Native FastAPI contract features with explicit route contract
  metadata.
- **C:** Hand-authored static OpenAPI.

## Decision framework (Framework A)

| Option | Native dependency leverage | Entropy / LOC / file reduction | Reliability / performance | Security / operability | DX / maintainability | Implementation tractability | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A: Keep bespoke schema surgery and path/method registries | 3 | 2 | 6 | 6 | 3 | 8 | 4.10 |
| **B: Native FastAPI contract features with explicit route contract metadata** | **10** | **8** | **9** | **9** | **10** | **7** | **9.10** |
| C: Hand-authored static OpenAPI | 4 | 5 | 5 | 7 | 4 | 4 | 4.85 |

## Decision

**Option B** is accepted.

Implementation commitments:

- Express responses, security, and models on routes with FastAPI-native APIs.
- Keep stable public `operationId` values explicit on route decorators.
- Delete the file-API OpenAPI mutation layer instead of replacing it with new
  post-processing.
- Treat `ErrorEnvelope` compatibility as top-level schema name plus on-wire
  fields, not subordinate helper-component topology.
- Branch `refactor/api-native-fastapi-openapi`.

## Related requirements

- [GFR-R4](../requirements.md#gfr-r4--public-contract-must-be-explicit)
- [GFR-R9](../requirements.md#gfr-r9--deterministic-build-and-verification)

## Consequences

1. **Positive:** Smaller contract layer, easier reviews, better alignment
   between code and emitted OpenAPI.
2. **Trade-offs:** Migration work to delete bespoke mutation; contract tests must
   follow route-declared behavior.
3. **Ongoing:** SDK generation and smoke tests remain mandatory gates.

## Changelog

- 2026-03-19: Canonical ADR ported from green-field pack ADR-0004.
