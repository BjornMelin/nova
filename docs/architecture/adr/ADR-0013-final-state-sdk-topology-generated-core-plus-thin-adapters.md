---
ADR: 0013
Title: Python-first SDK topology uses generated contract-core clients and defers TS/R productization
Status: Accepted
Version: 2.0
Date: 2026-03-05
Related:
  - "[ADR-0002: Treat OpenAPI as the contract and generate client SDKs from it](./ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0007: Auth API Contract](../spec/SPEC-0007-auth-api-contract.md)"
  - "[SPEC-0011: Python-first SDK architecture and deferred TS/R package map](../spec/SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
  - "[SPEC-0012: SDK governance for Python release-grade and deferred TS/R catalogs](../spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
  - "[Plan Master](../../plan/PLAN.md)"
References:
  - "[Semantic Versioning 2.0.0](https://semver.org/)"
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[openapi-fetch](https://openapi-ts.dev/openapi-fetch/)"
  - "[OpenAPI Generator typescript-fetch](https://openapi-generator.tech/docs/generators/typescript-fetch/)"
  - "[R lifecycle stages](https://lifecycle.r-lib.org/articles/stages.html)"
---

## Summary

Nova ships one release-grade public SDK surface in this wave: Python. All SDK
surfaces remain generated from canonical OpenAPI contracts, but TypeScript and R
stay generator-owned internal catalogs until a dedicated productization wave.

## Context

Nova already owns canonical OpenAPI contracts and generated-client smoke gates.
What it does not yet have for TypeScript and R is the full product boundary
needed for a public SDK release:

- stable published package/repository contracts
- release notes and semver governance per language
- downstream adoption and support commitments
- end-to-end CI/publish/documentation parity with Python

The repo may still contain generated TS/R artifacts for contract drift
detection, but greenfield finalization requires one truthful public stance.

## Alternatives

- A: Release Python as the only public SDK now and keep TS/R as internal
  generated catalogs until a later promotion wave (selected).
- B: Declare Python, TypeScript, and R all release-grade immediately.
- C: Remove all SDK artifacts and force every consumer to use raw HTTP.

## Decision framework

### Option scoring

| Option | Solution leverage (35%) | Application value (30%) | Maintenance and cognitive load (25%) | Architectural adaptability (10%) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | ---: |
| **A** | **9.6** | **9.4** | **9.5** | **9.3** | **9.49** |
| B | 6.8 | 7.0 | 4.9 | 6.7 | 6.38 |
| C | 4.2 | 4.5 | 6.1 | 5.8 | 4.93 |

Only options `>= 9.0` are accepted.

## Decision

Choose option A.

Implementation commitments:

- Canonical SDK generation inputs are Nova OpenAPI artifacts only.
- Public release-grade SDK packages for this wave are Python:
  - `nova_sdk_py_file`
  - `nova_sdk_py_auth`
- `nova_dash_bridge` remains a thin Python integration adapter over canonical
  Nova contracts.
- TypeScript and R packages remain in-repo generated catalogs used for
  drift detection, downstream planning, and future productization work, but
  they are not public release-grade SDKs in this wave.
- Canonical OpenAPI artifacts must expose stable snake_case `operationId`
  values and semantic tags so generated package/module names remain ergonomic
  across regeneration.
- Any pull request that changes OpenAPI contracts must regenerate Python
  artifacts via `scripts/release/generate_python_clients.py` and preserve
  internal TS/R catalog determinism via
  `scripts/release/generate_clients.py`.

## Related requirements

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)

## Consequences

1. Positive outcomes: one truthful public SDK posture, lower release complexity,
   and a clear hard-cut contract for downstream consumers.
2. Trade-offs/costs: TS/R consumers do not yet receive first-class published
   Nova SDK promises.
3. Ongoing considerations: a future TS/R promotion wave must add publishing,
   documentation, conformance, release policy, and support commitments in one
   change.

## Changelog

- 2026-03-05: Recast SDK governance to Python-first release-grade posture and
  deferred TS/R productization.
- 2026-03-05: Added stable SDK identifier/tagging and deterministic Python
  regeneration commitments.
