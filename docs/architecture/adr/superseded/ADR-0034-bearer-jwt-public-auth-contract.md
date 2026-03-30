---
ADR: 0034
Title: Green-field bearer JWT public auth contract
Status: Superseded
Version: 1.0
Date: 2026-03-19
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](../spec/superseded/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[ADR-0033: Green-field single runtime auth authority](./ADR-0033-single-runtime-auth-authority.md)"
  - "[SPEC-0027: Public HTTP contract revision and bearer auth](../spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md)"
  - "[Green-field simplification program](../../../history/2026-03-greenfield-wave-1-superseded/greenfield-simplification-program.md)"
References:
  - "[Green-field evidence (Framework A)](../../../history/2026-03-greenfield-wave-1-superseded/greenfield-evidence/DECISION_FRAMEWORKS_AND_SCORES.md)"
---

> **Superseded target draft**
>
> This draft was superseded before implementation. Use the active wave-2
> target-state ADR/SPEC set instead of this file for current authority.

## Summary

Public authorization context comes **only** from **bearer JWT** verification;
scope, tenant, and permissions are derived from **claims**. Session-style
surrogates in bodies and headers are removed. Winning option: **9.35/10**
(Framework A).

## Context

- Public requests previously carried `session_id`, `X-Session-Id`, `X-Scope-Id`,
  and related patterns parallel to JWT claims.
- Orchestration and authorization should follow verified identity, not parallel
  surrogate channels.
- Depends on [ADR-0033](./ADR-0033-single-runtime-auth-authority.md)
  for where verification runs.
- Execution order: program branch 2.

## Alternatives

- **A:** Keep same-origin + body/header session scope.
- **B:** Header-only session scope contract.
- **C:** Bearer JWT only; derive scope from claims.

## Decision framework (Framework A)

| Option | Native dependency leverage | Entropy / LOC / file reduction | Reliability / performance | Security / operability | DX / maintainability | Implementation tractability | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A: Keep same-origin + body/header session scope | 3 | 2 | 6 | 4 | 4 | 8 | 3.95 |
| B: Header-only session scope contract | 4 | 5 | 6 | 5 | 5 | 7 | 5.05 |
| **C: Bearer JWT only; derive scope from claims** | **10** | **9** | **9** | **10** | **9** | **8** | **9.35** |

## Decision

**Option C** is accepted.

Implementation commitments:

- Remove `session_id`, `X-Session-Id`, and `X-Scope-Id` from the public contract
  and OpenAPI.
- Do not preserve same-origin compatibility shims for removed scope carriers.
- Regenerate or adjust SDKs so they do not require removed parameters.
- Branch `feat/api-strip-session-scope-from-public-contract`.

## Related requirements

- [GFR-R2](../requirements.md#gfr-r2--auth-context-comes-from-verified-claims)
- [GFR-R4](../requirements.md#gfr-r4--public-contract-must-be-explicit)

## Consequences

1. **Positive:** Simpler API, fewer client mistakes, clearer security boundary.
2. **Trade-offs:** Breaking change; callers must send bearer tokens and rely on
   claims.
3. **Ongoing:** Contract tests and SDK conformance must enforce the stripped
   surface.

## Changelog

- 2026-03-19: Canonical ADR ported from green-field pack ADR-0002.
