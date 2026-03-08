---
ADR: 0013
Title: Multi-language SDK topology uses generated contract-core clients with retained TS/R foundations
Status: Accepted
Version: 3.0
Date: 2026-03-07
Related:
  - "[ADR-0002: Treat OpenAPI as the contract and generate client SDKs from it](./ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0007: Auth API Contract](../spec/SPEC-0007-auth-api-contract.md)"
  - "[SPEC-0011: Multi-language SDK architecture and package map](../spec/SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
  - "[SPEC-0012: SDK governance for multi-language conformance and compatibility](../spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
  - "[Plan Master](../../plan/PLAN.md)"
References:
  - "[Semantic Versioning 2.0.0](https://semver.org/)"
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[openapi-fetch](https://openapi-ts.dev/openapi-fetch/)"
  - "[OpenAPI Generator typescript-fetch](https://openapi-generator.tech/docs/generators/typescript-fetch/)"
  - "[R lifecycle stages](https://lifecycle.r-lib.org/articles/stages.html)"
---

## Summary

Nova must provide complete public SDKs for Python, TypeScript, and R. All SDK
surfaces remain generated from canonical OpenAPI contracts. Python SDKs are the
committed public client artifacts today, while TypeScript and R foundations
remain in-repo and must be preserved until their publish-ready parity work
lands.

## Context

Nova already owns canonical OpenAPI contracts and generated-client smoke gates.
What it still needs for TypeScript and R is the remaining product boundary work
needed for full public parity:

- stable published package/repository contracts
- release notes and semver governance per language
- downstream adoption and support commitments
- end-to-end CI/publish/documentation parity with Python

The repo must retain generated TS/R artifacts as future public-SDK foundations,
but greenfield finalization still requires one truthful authority chain:
canonical OpenAPI in, language-specific SDKs out, internal operations excluded
from client SDKs.

## Alternatives

- A: Keep Python public now and preserve TS/R only as internal catalogs until a
  later promotion wave.
- B: Require Python, TypeScript, and R as the target public SDK set while
  retaining TS/R scaffolding until their remaining publish-ready work lands
  (selected).
- C: Remove all SDK artifacts and force every consumer to use raw HTTP.

## Decision framework

### Option scoring

| Option | Solution leverage (35%) | Application value (30%) | Maintenance and cognitive load (25%) | Architectural adaptability (10%) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | ---: |
| A | 7.2 | 7.6 | 8.5 | 6.8 | 7.58 |
| **B** | **9.3** | **9.5** | **9.1** | **9.4** | **9.33** |
| C | 4.2 | 4.5 | 6.1 | 5.8 | 4.89 |

Only options `>= 9.0` are accepted.

## Decision

Choose option B.

Implementation commitments:

- Canonical SDK generation inputs are Nova OpenAPI artifacts only.
- Public per-service SDK packages are required in every supported language:
  - Python: `nova_sdk_py_file`, `nova_sdk_py_auth`
  - TypeScript foundation: `@nova/sdk-file-core`, `@nova/sdk-auth-core`, `@nova/sdk-fetch`
  - R foundation: `nova.sdk.r.file`, `nova.sdk.r.auth`
- `nova_dash_bridge` remains a thin Python integration adapter over canonical
  Nova contracts.
- TypeScript and R packages remain in-repo generated foundations used for
  drift detection and future completion work; they must not be deleted while
  Nova closes the remaining publish-ready gaps.
- TypeScript source installs run through the repo npm workspace, while staged
  CodeArtifact publication rewrites internal npm dependencies to exact semver
  values in publish-prepared artifacts.
- Canonical OpenAPI artifacts must expose stable snake_case `operationId`
  values and semantic tags so generated package/module names remain ergonomic
  across regeneration.
- Any pull request that changes OpenAPI contracts must regenerate Python
  artifacts via `scripts/release/generate_python_clients.py`, preserve TS/R
  foundation determinism via `scripts/release/generate_clients.py`, and keep
  internal-only endpoints out of client SDK generation.

## Related requirements

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)

## Consequences

1. Positive outcomes: one truthful target SDK posture, preserved TS/R delivery
   path, and a clear hard-cut contract for downstream consumers.
2. Trade-offs/costs: the repo now carries explicit unfinished TS/R parity work
   instead of hiding it behind a Python-only posture.
3. Ongoing considerations: TypeScript/R promotion still needs publishing,
   documentation, conformance, release policy, and support commitments.

## Changelog

- 2026-03-07: Recast SDK governance to target Python/TypeScript/R parity while
  preserving TS/R foundations.
- 2026-03-05: Added stable SDK identifier/tagging and deterministic regeneration
  commitments.
