---
ADR: 0013
Title: Public Python SDK topology uses generated contract-core clients while TypeScript remains generated/private and R stays deferred
Status: Accepted
Version: 2.1
Date: 2026-03-09
Related:
  - "[ADR-0002: Treat OpenAPI as the contract and generate client SDKs from it](./ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0007: Auth API Contract](../spec/SPEC-0007-auth-api-contract.md)"
  - "[SPEC-0011: Public Python SDK architecture with generated/private TypeScript and deferred R package map](../spec/SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
  - "[SPEC-0012: SDK governance for Python public plus generated/private TypeScript and deferred R catalogs](../spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
  - "[Plan Master](../../plan/PLAN.md)"
References:
  - "[Semantic Versioning 2.0.0](https://semver.org/)"
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[openapi-fetch](https://openapi-ts.dev/openapi-fetch/)"
  - "[OpenAPI Generator typescript-fetch](https://openapi-generator.tech/docs/generators/typescript-fetch/)"
  - "[R lifecycle stages](https://lifecycle.r-lib.org/articles/stages.html)"
---

## Summary

Nova ships the release-grade public Python SDK in this wave. TypeScript remains
a generated/private-distribution SDK contract surface, and R stays a
generator-owned internal catalog until dedicated promotion waves.

## Context

Nova already owns canonical OpenAPI contracts and generated-client smoke gates.
The repo may contain generated TypeScript and R artifacts for contract drift
detection, private CodeArtifact publication, and future promotion planning, but
greenfield finalization requires one truthful public stance now.

## Alternatives

- A: Remove all SDK artifacts and force every consumer to use raw HTTP.
- B: Keep Python as the only public SDK while TypeScript remains
  generated/private and R stays deferred (selected).
- C: Promote Python and TypeScript together now while keeping R deferred.

## Decision framework

### Option scoring

| Option | Solution leverage (35%) | Application value (30%) | Maintenance and cognitive load (25%) | Architectural adaptability (10%) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | ---: |
| A | 4.2 | 4.5 | 6.1 | 5.8 | 4.93 |
| **B** | **9.3** | **9.1** | **9.0** | **9.2** | **9.14** |
| C | 8.1 | 8.4 | 7.2 | 8.4 | 8.01 |

Only options `>= 9.0` are accepted.

## Decision

Choose option B.

Implementation commitments:

- Canonical SDK generation inputs are Nova OpenAPI artifacts only.
- Public release-grade SDK packages for this wave are:
  - `nova_sdk_py_file`
  - `nova_sdk_py_auth`
- `nova_dash_bridge` remains a thin Python integration adapter over canonical
  Nova contracts, using `nova_file_api.public` as its in-process runtime seam.
- `@nova/sdk-file`, `@nova/sdk-auth`, and `@nova/sdk-fetch` remain
  generator-owned TypeScript packages used for private distribution and
  conformance.
- TypeScript SDKs remain runtime-lean and do not bundle validation libraries.
- TypeScript `types` subpaths expose curated operation helpers and reachable
  public schema aliases only; raw whole-spec OpenAPI aliases are generator
  implementation detail and not public contract authority.
- Multi-media request bodies in the TypeScript SDKs must use explicit
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

1. Positive outcomes: truthful public SDK posture, lower documentation drift,
   and a clear hard-cut contract for consumers.
2. Trade-offs/costs: TypeScript remains supported and tested, but public
   support guarantees stay limited to Python in this wave.
3. Ongoing considerations: TypeScript and R still need future promotion waves
   that add public publishing, documentation, conformance posture, release
   policy, and support commitments in one change.

## Changelog

- 2026-03-05: Recast SDK governance to Python-first release-grade posture and
  deferred TS/R productization.
- 2026-03-05: Added stable SDK identifier/tagging and deterministic Python
  regeneration commitments.
- 2026-03-09: Reaffirmed Python-only public SDK posture while keeping
  TypeScript generated/private and R deferred.
