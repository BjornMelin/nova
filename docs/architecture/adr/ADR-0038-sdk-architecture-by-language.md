---
ADR: 0038
Title: Green-field SDK architecture by language
Status: Accepted
Version: 1.0
Date: 2026-03-19
Supersedes: "[ADR-0013: Final-state SDK topology (superseded)](./superseded/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
Related:
  - "[SPEC-0029: SDK architecture and artifact contract](../spec/SPEC-0029-sdk-architecture-and-artifact-contract.md)"
  - "[ADR-0013: Final-state SDK topology (superseded)](./superseded/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
  - "[SPEC-0011: Multi-language SDK architecture and package map (superseded)](../spec/superseded/SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
  - "[SPEC-0012: SDK conformance, versioning, and compatibility governance](../spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
  - "[ADR-0033: Green-field single runtime auth authority](./ADR-0033-single-runtime-auth-authority.md)"
  - "[Green-field simplification program](../../plan/greenfield-simplification-program.md)"
References:
  - "[Green-field evidence (Framework B)](../../plan/greenfield-evidence/DECISION_FRAMEWORKS_AND_SCORES.md)"
  - "[Rejected and deferred options](../../plan/greenfield-evidence/REJECTED_AND_DEFERRED_OPTIONS.md)"
---

## Summary

Per-language public SDKs use **idiomatic, generator-native** stacks: TypeScript
uses **`openapi-typescript` + `openapi-fetch`**; Python keeps
**`openapi-python-client`** with **config + minimal templates**; R uses a
**thin `httr2`** package, not the OpenAPI Generator R beta client as the primary
path. Each language has **one** public SDK family (no auth-only SDKs). Winning
options score **≥ 9.10** under Framework B (see evidence file).

## Context

- Nova maintained large custom generator/runtime layers; ecosystems provide
  better-maintained building blocks.
- Auth-only SDK packages go away with
  [ADR-0033](./ADR-0033-single-runtime-auth-authority.md).
- TypeScript and R moves must **preserve**
  [SPEC-0029](../spec/SPEC-0029-sdk-architecture-and-artifact-contract.md)
  / [SPEC-0012](../spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)
  and `AGENTS.md` invariants: no `zod` in generated TS SDKs, no package-root
  `"."` exports, no barrel re-exports, explicit `contentType` for multi-media
  bodies, `x-nova-sdk-visibility: internal` exclusions.
- Execution order: program branches 7–9.

## Decision

- **TypeScript:** Adopt **openapi-typescript** + **openapi-fetch**; remove the
  custom `@nova/sdk-fetch` runtime and bulky bespoke generator glue while
  keeping conformance governance.
- **Python:** Keep **openapi-python-client**; move customization into generator
  config and small template overrides; delete large post-generation patch
  scripts where possible.
- **R:** Ship a thin **httr2**-based package with minimal generated metadata and
  idiomatic helpers; do **not** adopt the beta OpenAPI Generator R client as the
  primary path.

## Decision framework (Framework B)

Framework B weights (see evidence): language ecosystem fit 20%, consumer
ergonomics 15%, maintenance burden reduction 25%, type safety 15%, native
tooling leverage 15%, migration clarity 10%.

### TypeScript — winner **openapi-typescript + openapi-fetch** — **9.50/10**

### Python — winner **openapi-python-client + config/templates** — **9.10/10**

### R — winner **thin httr2 + minimal codegen** — **9.10/10**

## Implementation commitments

- Branches `refactor/sdk-typescript-openapi-fetch`,
  `refactor/sdk-python-template-thin`,
  `refactor/sdk-r-httr2-thin-client`.
- Conformance with
  [SPEC-0029](../spec/SPEC-0029-sdk-architecture-and-artifact-contract.md).

## Related requirements

- [GFR-R6](../requirements.md#gfr-r6--sdks-must-feel-native-per-language)
- [GFR-R8](../requirements.md#gfr-r8--one-client-artifact-family-per-language)
- [GFR-R9](../requirements.md#gfr-r9--deterministic-build-and-verification)

## Consequences

1. **Positive:** Less generator glue, better ecosystem fit, smaller maintenance
   surface.
2. **Trade-offs:** Breaking changes across SDK majors; consumers migrate import
   paths and auth assembly.
3. **Ongoing:** npm / R / CodeArtifact release lanes stay aligned with OpenAPI
   export checks.

## Changelog

- 2026-03-19: Recorded formal supersession of [ADR-0013](./superseded/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md) (moved to `superseded/`).
- 2026-03-19: Canonical ADR ported from green-field pack ADR-0006; explicit
  SPEC-0029/SPEC-0012 invariant preservation.
