---
ADR: 0013
Title: Public Python/TypeScript SDK topology uses generated contract-core clients and defers R productization
Status: Accepted
Version: 2.0
Date: 2026-03-05
Related:
  - "[ADR-0002: Treat OpenAPI as the contract and generate client SDKs from it](./ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0007: Auth API Contract](../spec/SPEC-0007-auth-api-contract.md)"
  - "[SPEC-0011: Public Python/TypeScript SDK architecture and deferred R package map](../spec/SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
  - "[SPEC-0012: SDK governance for public Python/TypeScript SDKs and deferred R catalogs](../spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
  - "[Plan Master](../../plan/PLAN.md)"
References:
  - "[Semantic Versioning 2.0.0](https://semver.org/)"
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[openapi-fetch](https://openapi-ts.dev/openapi-fetch/)"
  - "[OpenAPI Generator typescript-fetch](https://openapi-generator.tech/docs/generators/typescript-fetch/)"
  - "[R lifecycle stages](https://lifecycle.r-lib.org/articles/stages.html)"
---

## Summary

Nova ships release-grade public SDK surfaces for Python and TypeScript in this
wave. All SDK surfaces remain generated from canonical OpenAPI contracts, while
R stays a generator-owned internal catalog until a dedicated productization
wave.

## Context

Nova already owns canonical OpenAPI contracts and generated-client smoke gates.
The remaining gap is R productization. TypeScript now has the required public
package, CI, and release boundary:

- stable published package/repository contracts
- release notes and semver governance per language
- downstream adoption and support commitments
- end-to-end CI/publish/documentation parity with Python

The repo may still contain generated TS/R artifacts for contract drift
detection, but greenfield finalization requires one truthful public stance.

## Alternatives

- A: Release Python as the only public SDK now and keep TypeScript/R as internal
  generated catalogs until a later promotion wave.
- B: Declare Python and TypeScript release-grade now while keeping R deferred
  (selected).
- C: Remove all SDK artifacts and force every consumer to use raw HTTP.

## Decision framework

### Option scoring

| Option | Solution leverage (35%) | Application value (30%) | Maintenance and cognitive load (25%) | Architectural adaptability (10%) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | ---: |
| A | 8.2 | 7.8 | 7.6 | 8.0 | 7.89 |
| **B** | **9.4** | **9.3** | **8.9** | **9.1** | **9.19** |
| C | 4.2 | 4.5 | 6.1 | 5.8 | 4.93 |

Only options `>= 9.0` are accepted.

## Decision

Choose option B.

Implementation commitments:

- Canonical SDK generation inputs are Nova OpenAPI artifacts only.
- Public release-grade SDK packages for this wave are Python and TypeScript:
  - `nova_sdk_py_file`
  - `nova_sdk_py_auth`
  - `@nova/sdk-file`
  - `@nova/sdk-auth`
- `nova_dash_bridge` remains a thin Python integration adapter over canonical
  Nova contracts.
- `@nova/sdk-fetch` remains a generator-owned runtime helper used by the public
  TypeScript SDKs.
- TypeScript SDKs are runtime-lean and do not bundle validation libraries.
- Public TypeScript `types` subpaths expose curated operation helpers and
  reachable public schema aliases only; raw whole-spec OpenAPI aliases are
  generator implementation detail and not public contract authority.
- Multi-media request bodies in the public TypeScript SDKs must use explicit
  generated `contentType` selection when request-body shape alone is
  insufficient to determine the correct wire format.
- R packages remain in-repo generated catalogs used for drift detection,
  downstream planning, and future productization work, but they are not public
  release-grade SDKs in this wave.
- Canonical OpenAPI artifacts must expose stable snake_case `operationId`
  values and semantic tags so generated package/module names remain ergonomic
  across regeneration.
- Any pull request that changes OpenAPI contracts must regenerate Python and
  TypeScript artifacts and preserve R catalog determinism via
  `scripts/release/generate_clients.py`.

## Related requirements

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)

## Consequences

1. Positive outcomes: truthful public SDK posture for the already-supported
   TypeScript surface, lower downstream friction, and a clear hard-cut contract
   for consumers.
2. Trade-offs/costs: Nova now owns TypeScript semver, conformance, and publish
   guarantees alongside Python.
3. Ongoing considerations: R still needs a future promotion wave that adds
   publishing, documentation, conformance, release policy, and support
   commitments in one change.

## Changelog

- 2026-03-05: Recast SDK governance to Python-first release-grade posture and
  deferred TS/R productization.
- 2026-03-05: Added stable SDK identifier/tagging and deterministic Python
  regeneration commitments.
- 2026-03-09: Promoted TypeScript to a public release-grade SDK surface and
  kept R deferred.
