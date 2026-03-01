---
ADR: 0013
Title: Final-state SDK topology uses generated contract-core clients plus thin language adapters
Status: Accepted
Version: 1.0
Date: 2026-02-28
Related:
  - "[ADR-0002: Treat OpenAPI as the contract and generate client SDKs from it](./ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0007: Auth API Contract](../spec/SPEC-0007-auth-api-contract.md)"
  - "[SPEC-0011: Multi-language SDK architecture and package map](../spec/SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
  - "[SPEC-0012: SDK conformance, versioning, and compatibility governance](../spec/SPEC-0012-sdk-conformance-versioning-and-compatibility-governance.md)"
  - "[Plan Master](../../plan/PLAN.md)"
  - "[Hard Cutover Checklist](../../plan/release/HARD-CUTOVER-CHECKLIST.md)"
References:
  - "[Semantic Versioning 2.0.0](https://semver.org/)"
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[openapi-fetch](https://openapi-ts.dev/openapi-fetch/)"
  - "[OpenAPI Generator typescript-fetch](https://openapi-generator.tech/docs/generators/typescript-fetch/)"
  - "[R lifecycle stages](https://lifecycle.r-lib.org/articles/stages.html)"
---

## Summary

Nova SDKs will use a single final-state topology: generated language-core clients from canonical OpenAPI contracts, plus thin language/framework adapters that contain no protocol authority. This is the only topology meeting final-state governance and >=9.0 decision threshold.

## Context

Nova already established OpenAPI contract ownership and generated-client smoke gates, but downstream consumers currently show drift patterns:

- Python Dash (`dash-pca`) contains handwritten token-verify client logic and envelope mapping.
- R Shiny (`shiny-auth-mmm`) contains a separate handwritten verify client with divergent failure handling semantics.
- TypeScript consumers currently rely on local app patterns instead of a canonical Nova package map.

Key constraints:

- Final-state only (no shims/transitional wrappers/back-compat scaffolding).
- Multi-language support is required for Python (Dash), TypeScript (Next), and R (Shiny).
- Contract compatibility and deprecation policy must be explicit and enforceable via CI.
- Requirement baseline includes OpenAPI contract ownership and fail-closed auth semantics.

Adversarial consensus evidence (zen.consensus runs) converged on one admissible option:

- Run 1 (OpenAI GPT-5.2 against): Option A = 9.3; B = 6.4; C = 7.6.
- Run 2 (Gemini 3 Flash against): Option A strongly preferred; B/C below production target.
- Run 3 (Grok 4.1 against): Option A = 9.5; B = 4.0; C = 2.0.

## Alternatives

- A: Generated contract-core SDKs per language plus thin adapters (selected).
- B: Handwritten SDK/client implementations per app repo.
- C: SDKless sidecar/gateway-only integration model.

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| **A** | **9.7** | **9.4** | **9.3** | **9.2** | **9.45** |
| B | 6.2 | 6.5 | 4.8 | 5.9 | 5.97 |
| C | 5.8 | 5.7 | 6.1 | 6.4 | 5.93 |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

## Decision

Choose option A.

Implementation commitments:

- Canonical language-core SDKs are generated from Nova OpenAPI artifacts only.
- Thin adapters are allowed only for language idioms/framework integration, not contract authority.
- Python, TypeScript, and R SDK surfaces and release boundaries are defined in SPEC-0011.
- Conformance fixtures, compatibility gates, and deprecation policy are mandatory per SPEC-0012.
- Any pull request that changes OpenAPI contract MUST run SDK regeneration + conformance checks.

## Related Requirements

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)

## Consequences

1. Positive outcomes: one contract authority across Dash/Shiny/TS consumers; lower drift and faster release confidence.
2. Trade-offs/costs: requires strict OpenAPI hygiene and disciplined adapter boundaries.
3. Ongoing considerations: schema governance and deprecation windows must be enforced continuously; adapter creep is treated as architecture non-compliance.

## Changelog

- 2026-02-28: Initial accepted ADR defining final-state SDK topology and governance commitments.

---

## ADR Completion Checklist

- [x] All placeholders (`<…>`) and bracketed guidance are removed/replaced.
- [x] All links are markdown-clickable and resolve to valid local docs or sources.
- [x] Context includes concrete constraints, not generic boilerplate.
- [x] Alternatives are decision-relevant and scored consistently.
- [x] Winning row is bold and matches the Decision section.
- [x] Accepted/Implemented ADR score is `>= 9.0`.
- [x] Related requirements link to exact requirement anchors.
- [x] Consequences include both benefits and trade-offs.
