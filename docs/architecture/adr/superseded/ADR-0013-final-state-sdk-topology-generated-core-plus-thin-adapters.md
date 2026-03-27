---
ADR: 0013
Title: Public Python SDK topology uses generated contract-core clients while TypeScript is release-grade in CodeArtifact and R is a first-class internal release line
Status: Superseded
Version: 3.0
Date: 2026-03-18
Superseded-by: "[ADR-0038: Green-field SDK architecture by language](../ADR-0038-sdk-architecture-by-language.md)"
Related:
  - "[ADR-0002: Treat OpenAPI as the contract and generate client SDKs from it](../ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0027: Public HTTP contract revision and bearer auth](../../spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md)"
  - "[SPEC-0011: Public Python SDK architecture with release-grade TypeScript and first-class internal R package map (superseded)](../../spec/superseded/SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
  - "[SPEC-0012: SDK governance for Python public, release-grade TypeScript, and first-class internal R packages](../../spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
  - "[Plan Master](../../../plan/PLAN.md)"
References:
  - "[Semantic Versioning 2.0.0](https://semver.org/)"
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[openapi-fetch](https://openapi-ts.dev/openapi-fetch/)"
  - "[OpenAPI Generator typescript-fetch](https://openapi-generator.tech/docs/generators/typescript-fetch/)"
  - "[R lifecycle stages](https://lifecycle.r-lib.org/articles/stages.html)"
---

## Summary

Nova ships the release-grade public Python SDK in this wave. TypeScript is
release-grade within Nova's existing CodeArtifact staged/prod system while
remaining generator-owned and subpath-only, and R is a first-class internal
release artifact line with real package scaffolds, logical format `r`,
CodeArtifact generic packages, and signed tarball evidence.

## Context

Nova already owns canonical OpenAPI contracts and generated-client smoke gates.
The repo may contain generated TypeScript and R artifacts for contract drift
detection, CodeArtifact staged/prod publication, and release-evidence
planning, but greenfield finalization requires one truthful public stance now.

## Alternatives

- A: Remove all SDK artifacts and force every consumer to use raw HTTP.
- B: Keep Python public while finalizing TypeScript in CodeArtifact and
  promoting R to a first-class internal release line (selected).
- C: Defer TypeScript and R until a later wave.

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
  - the legacy split Python file SDK package
  - the legacy split Python auth SDK package
- `nova_dash_bridge` remains a thin Python integration adapter over canonical
  Nova contracts, using `nova_file_api.public` as its in-process runtime seam.
- `@nova/sdk-file`, `@nova/sdk-auth`, and `@nova/sdk-fetch` remain
  generator-owned TypeScript packages, but they are release-grade within Nova's
  CodeArtifact staged/prod system and remain subpath-only.
- TypeScript SDKs remain runtime-lean and do not bundle validation libraries.
- TypeScript `types` subpaths expose curated operation helpers and reachable
  public schema aliases only; raw whole-spec OpenAPI aliases are generator
  implementation detail and not public contract authority.
- Multi-media request bodies in the TypeScript SDKs must use explicit
  generated `contentType` selection when request-body shape alone is
  insufficient to determine the correct wire format.
- R packages are real package scaffolds, released as first-class internal
  artifacts with logical format `r`, transported through CodeArtifact generic
  packages, and accompanied by signed tarball evidence.
- Canonical OpenAPI artifacts must expose stable snake_case `operationId`
  values and semantic tags so generated package/module names remain ergonomic
  across regeneration.
- Any pull request that changes OpenAPI contracts must regenerate Python and
  TypeScript artifacts and preserve R package determinism via
  `scripts/release/generate_clients.py` plus the R packaging and evidence
  workflow.

## Related requirements

- [FR-0005](../../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../../requirements.md#ir-0003-optional-remote-auth-service)

## Consequences

1. Positive outcomes: truthful public SDK posture, lower documentation drift,
   and a clear hard-cut contract for consumers.
2. Trade-offs/costs: TypeScript remains supported and tested as a release-grade
   CodeArtifact line, but public support guarantees stay limited to Python in
   this wave.
3. Ongoing considerations: R remains internal, so support commitments attach to
   the release artifact line rather than public CRAN-style publishing.

## Changelog

- 2026-03-19: Superseded by [ADR-0038](../ADR-0038-sdk-architecture-by-language.md); retained for traceability.
- 2026-03-18: Recast SDK governance to final Python public, TypeScript
  CodeArtifact, and first-class internal R release posture.
- 2026-03-05: Added stable SDK identifier/tagging and deterministic Python
  regeneration commitments.
