---
ADR: 0033
Title: Green-field single runtime auth authority
Status: Accepted
Version: 1.0
Date: 2026-03-19
Supersedes: "[ADR-0005: Add dedicated nova-auth-api service (superseded)](./superseded/ADR-0005-add-dedicated-nova-auth-api-service.md)"
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](../spec/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0034: Green-field bearer JWT public auth contract](./ADR-0034-bearer-jwt-public-auth-contract.md)"
  - "[SPEC-0027: Public HTTP contract revision and bearer auth](../spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md)"
  - "[Green-field simplification program](../../plan/greenfield-simplification-program.md)"
  - "[Green-field evidence (Framework A)](../../plan/greenfield-evidence/DECISION_FRAMEWORKS_AND_SCORES.md)"
References:
  - "[Rejected and deferred options (pack copy)](../../plan/greenfield-evidence/REJECTED_AND_DEFERRED_OPTIONS.md)"
---

## Summary

Nova uses **one** public API runtime for JWT verification and principal
normalization and **removes** the standalone auth service and auth-only SDK /
OpenAPI artifacts. Winning option scores **9.70/10** under Framework A (code /
runtime simplification) documented in green-field evidence.

## Context

- Authentication was split across `nova_file_api` and `nova_auth_api`; both
  verified JWTs and normalized principals.
- Async-native verifier integration inside the app removes duplicated packages,
  images, releases, and contracts.
- Edge-only JWT enforcement is rejected as the **primary** auth layer (see
  green-field evidence §1).
- Program sequencing is tracked in
  [greenfield-simplification-program.md](../../plan/greenfield-simplification-program.md).

## Alternatives

- **A:** Keep dedicated auth service + remote verification.
- **B:** Keep in-app auth but preserve sync verifier + multi-mode complexity.
- **C:** Inline async verifier in file API and delete auth service.

## Decision framework (Framework A)

| Criterion | Weight |
| --- | --- |
| Native dependency leverage | 25 |
| Entropy / LOC / file reduction | 20 |
| Reliability / performance | 20 |
| Security / operability | 15 |
| DX / maintainability | 15 |
| Implementation tractability | 5 |

### Auth topology -- option scoring

| Option | Native dependency leverage | Entropy / LOC / file reduction | Reliability / performance | Security / operability | DX / maintainability | Implementation tractability | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A: Keep dedicated auth service + remote verification | 3 | 2 | 5 | 6 | 4 | 8 | 4.05 |
| B: Keep in-app auth but preserve sync verifier + multi-mode complexity | 5 | 5 | 6 | 7 | 5 | 7 | 5.60 |
| **C: Inline async verifier in file API and delete auth service** | **10** | **10** | **9** | **10** | **10** | **8** | **9.70** |

## Decision

**Option C** is accepted.

Implementation commitments:

- Implement async-native JWT verification and FastAPI dependency integration in
  the file API.
- Remove `nova_auth_api` deployment units, images, and dedicated auth route
  surfaces from the target architecture.
- Delete auth-only SDK families and auth-only OpenAPI artifacts; fold any
  remaining token semantics into the file API contract.
- Implementation is tracked by the green-field simplification program and the
  active runtime/spec authority set, not by `.agents/**` prompt files.

## Related requirements

- [GFR-R1](../requirements.md#gfr-r1--single-public-runtime-authority)
- [GFR-R3](../requirements.md#gfr-r3--async-correctness-is-mandatory)
- [GFR-R8](../requirements.md#gfr-r8--one-client-artifact-family-per-language)

## Consequences

1. **Positive:** Smaller topology, one implementation to test, no internal hop to
   a second service for verification, simpler releases.
2. **Trade-offs:** Breaking change for consumers of auth-only APIs and
   packages.
3. **Ongoing:** Coordinate with [ADR-0034](./ADR-0034-bearer-jwt-public-auth-contract.md)
   for public contract shape.

## Changelog

- 2026-03-19: Canonical ADR ported from green-field pack ADR-0001; supersedes
  ADR-0005.
