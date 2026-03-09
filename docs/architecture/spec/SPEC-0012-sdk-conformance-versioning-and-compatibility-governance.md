---
Spec: 0012
Title: SDK governance for Python release-grade and deferred TS/R catalogs
Status: Active
Version: 2.0
Date: 2026-03-05
Related:
  - "[ADR-0013: Python-first SDK topology uses generated contract-core clients and defers TS/R productization](../adr/ADR-0013-final-state-sdk-topology-generated-core-plus-thin-adapters.md)"
  - "[SPEC-0011: Python-first SDK architecture and deferred TS/R package map](./SPEC-0011-multi-language-sdk-architecture-and-package-map.md)"
  - "[SPEC-0004: CI/CD and docs](./SPEC-0004-ci-cd-and-docs.md)"
  - "[Hard Cutover Checklist](../../plan/release/HARD-CUTOVER-CHECKLIST.md)"
References:
  - "[Semantic Versioning 2.0.0](https://semver.org/)"
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[R lifecycle stages](https://lifecycle.r-lib.org/articles/stages.html)"
---

## 1. Scope

Defines conformance, release/versioning policy, deprecation policy, and API
compatibility governance for the current Nova SDK posture:

- Python public release-grade SDK packages
- internal/generated TypeScript and R catalogs

## 2. Conformance fixture strategy

### 2.1 Fixture source of truth

Conformance fixtures are generated from canonical OpenAPI contracts and
committed under a Nova-owned fixtures path.

Fixture groups:

- request shapes
- response shapes
- error envelope shapes
- auth verify happy/failure paths
- optional introspection enabled/disabled behavior

### 2.2 Language conformance suites

Required CI posture:

- Python: release-grade conformance gate covering model/operation compile,
  fixture decode/encode, generated-client smoke, and auth error mapping
- TypeScript: internal catalog gate covering fixture typing and generated
  catalog drift only
- R: internal catalog gate covering generated artifact drift and fixture
  roundtrip only

Nova repository lanes:

- `.github/workflows/conformance-clients.yml`
- `packages/contracts/typescript/src/conformance.ts`
- `scripts/release/generate_clients.py --check`
- `scripts/release/generate_python_clients.py --check`

### 2.3 Golden-path scenarios

Minimum shared scenarios:

1. `verify_token` success with normalized principal shape
2. `verify_token` `401` with RFC6750-compatible challenge pass-through where
   available
3. `verify_token` `403` insufficient authorization
4. file transfer initiate/sign/complete roundtrip payload conformance
5. queue enqueue error envelope (`queue_unavailable`) shape stability

## 3. Versioning and release policy

### 3.1 Public SemVer requirements

Public Python SDK packages follow Semantic Versioning 2.0.0:

- MAJOR for backward-incompatible public API or contract changes
- MINOR for backward-compatible API additions
- PATCH for backward-compatible fixes only

Breaking examples for public Python SDK packages include:

- OpenAPI tag changes that move generated endpoint modules/packages
- `operationId` renames that change generated function names
- contract removals or incompatible schema changes

### 3.2 Internal catalog version posture

TypeScript and R catalogs are not public compatibility authority in this wave.
They must remain deterministic from OpenAPI inputs, but they do not imply a
public support or publishing contract.

### 3.3 Release cadence and promotion

- Python releases are produced by Nova CI only after public conformance suites
  pass.
- Release notes must include explicit breaking/additive/fix classification for
  public Python packages.
- Generated Python artifacts are immutable after release.
- TS/R productization is deferred and must be completed in a future dedicated
  wave using `.agents/prompts/deferred-ts-r-sdk-finalization-gpt54-xhigh.md`
  as the implementation handoff prompt.

## 4. Deprecation policy

### 4.1 API deprecation baseline

- Deprecated operations/fields must be marked in OpenAPI with deprecation
  metadata and changelog note.
- Deprecation notice window: minimum one MINOR release before removal in next
  MAJOR for public Python surfaces.
- Runtime behavior during deprecation must remain contract-compatible.

### 4.2 SDK deprecation baseline

- Python public methods scheduled for removal must emit warnings-based
  deprecation.
- TS/R catalog evolution is internal until those languages are promoted to
  public SDK status.

## 5. API/contract governance and compatibility policy

### 5.1 Contract change classification

Every OpenAPI delta is classified as:

- non-breaking
- potentially breaking (requires architecture review)
- breaking (MAJOR required for affected public packages)

### 5.2 Required gates

A pull request modifying OpenAPI contracts must pass:

- schema validity checks
- explicit change classification
- regenerated Python SDK diffs
- Python generated-client smoke
- internal TS/R generated catalog drift gate via
  `scripts/release/generate_clients.py --check`
- committed Python SDK drift gate via
  `scripts/release/generate_python_clients.py --check`

### 5.3 Blocking conditions

Merge must be blocked if any of the following occur:

- Python fixture compatibility regression without MAJOR bump
- error envelope shape drift (`error.code/message/request_id`) in a non-major
  public release
- adapter introduces contract fork or local authority logic

## 6. Governance ownership

- Nova architecture owners approve contract and governance changes.
- Consumer repos cannot override contract semantics.
- Exceptions require explicit ADR update; temporary compatibility layers are
  disallowed.

## 7. Traceability

- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
- [IR-0003](../requirements.md#ir-0003-optional-remote-auth-service)
