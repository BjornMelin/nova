---
Spec: 0012
Title: SDK conformance, versioning, and compatibility governance
Status: Active
Version: 1.0
Date: 2026-02-28
Related:
  - "[ADR-0013: Final-state SDK topology uses generated contract-core clients plus thin language adapters](../adr/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
  - "[SPEC-0011: Multi-language SDK architecture and package map](./SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
  - "[SPEC-0004: CI/CD and docs](./SPEC-0004-ci-cd-and-docs.md)"
  - "[Hard Cutover Checklist](../../plan/release/HARD-CUTOVER-CHECKLIST.md)"
References:
  - "[Semantic Versioning 2.0.0](https://semver.org/)"
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[R lifecycle stages](https://lifecycle.r-lib.org/articles/stages.html)"
---

## 1. Scope

This spec defines mandatory conformance fixtures, release/versioning policy, deprecation policy, and API compatibility governance for Nova SDKs across Python, TypeScript, and R.

## 2. Conformance fixture strategy

### 2.1 Fixture source of truth

Conformance fixtures are generated from canonical OpenAPI contracts and committed under a Nova-owned fixtures path.

Fixture groups:

- request shapes
- response shapes
- error envelope shapes
- auth verify happy/failure paths
- optional introspection enabled/disabled behavior

### 2.2 Language conformance suites

Each language SDK MUST run contract conformance suites in CI:

- Python: model/operation compile + fixture decode/encode + auth error mapping
- TypeScript: `tsc --noEmit` + fixture typing + runtime response narrowing for success/error envelopes
- R: fixture JSON roundtrip + client request generation + response mapping validation

### 2.3 Golden-path scenarios

Minimum shared scenarios:

1. `verify_token` success with normalized principal shape
2. `verify_token` 401 with RFC6750-compatible challenge pass-through where available
3. `verify_token` 403 insufficient authorization
4. file transfer initiate/sign/complete roundtrip payload conformance
5. queue enqueue error envelope (`queue_unavailable`) shape stability

## 3. Versioning and release policy

### 3.1 SemVer requirements

All SDK packages MUST follow Semantic Versioning 2.0.0:

- MAJOR for backward-incompatible public API or contract changes
- MINOR for backward-compatible API additions
- PATCH for backward-compatible fixes only

### 3.2 Multi-package coordination

- Contract-breaking OpenAPI changes MUST trigger MAJOR bump for all affected language-core packages.
- Adapter-only internal changes MAY bump PATCH if public adapter API is unchanged.
- If generated model signatures change incompatibly, this is MAJOR even when endpoint path remains unchanged.

### 3.3 Release cadence and promotion

- Releases are produced by Nova CI only after conformance suites pass.
- Release notes MUST include explicit “breaking/additive/fix” classification per package.
- Generated SDK artifacts are immutable after release.

## 4. Deprecation policy

### 4.1 API deprecation baseline

- Deprecated operations/fields MUST be marked in OpenAPI with deprecation metadata and changelog note.
- Deprecation notice window: minimum one MINOR release before removal in next MAJOR.
- Runtime behavior during deprecation MUST remain contract-compatible.

### 4.2 SDK deprecation baseline

- SDK public methods scheduled for removal MUST emit language-idiomatic deprecation notices:
  - Python: warnings-based deprecation
  - TypeScript: `@deprecated` annotations
  - R: lifecycle deprecation tags/messages
- Removal occurs only in MAJOR release after published notice window.

## 5. API/contract governance and compatibility policy

### 5.1 Contract change classification

Every OpenAPI delta is classified as:

- Non-breaking
- Potentially breaking (requires architecture review)
- Breaking (MAJOR required)

### 5.2 Required gates

A pull request modifying OpenAPI contracts MUST pass:

- schema validity checks
- explicit change classification
- regenerated SDK diffs for Python/TypeScript/R
- language conformance fixtures
- generated-client smoke checks

### 5.3 Blocking conditions

Merge MUST be blocked if any of the following occur:

- fixture compatibility regression without MAJOR bump
- error envelope shape drift (`error.code/message/request_id`) in non-major release
- adapter introduces contract fork or local authority logic

## 6. Governance ownership

- Nova architecture owners approve contract and governance changes.
- Consumer repos cannot override contract semantics.
- Exceptions require explicit ADR update; temporary/transitional compatibility layers are disallowed.

## 7. Traceability

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)
