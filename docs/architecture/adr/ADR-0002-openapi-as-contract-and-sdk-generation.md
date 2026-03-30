---
ADR: 0002
Title: Treat OpenAPI as the contract and generate client SDKs from it
Status: Accepted
Version: 1.2
Date: 2026-02-12
Related:
  - "[ADR-0000: Implement the File Transfer API as a FastAPI service](./ADR-0000-fastapi-microservice.md)"
  - "[ADR-0003: API documentation site uses MkDocs Material and Scalar API Reference](./ADR-0003-api-docs-site-mkdocs-material-plus-scalar.md)"
  - "[SPEC-0000: HTTP API contract](../spec/superseded/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0004: CI/CD and documentation automation](../spec/SPEC-0004-ci-cd-and-docs.md)"
References:
  - "[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)"
  - "[FastAPI OpenAPI URL configuration](https://fastapi.tiangolo.com/tutorial/metadata/#openapi-url)"
  - "[@hey-api/openapi-ts](https://heyapi.dev/openapi-ts/get-started)"
  - "[OpenAPI Generator](https://openapi-generator.tech/)"
---

## Summary

The OpenAPI schema emitted by the service is the source of truth for endpoint and
model contracts. Client artifacts for TypeScript and R are generated from that schema
instead of being handwritten.

## Context

The API is consumed by multiple stacks (Next.js, Dash, R Shiny, and other HTTP clients).
When contracts are duplicated across languages, drift appears in validation behavior,
field naming, optionality, and error handling semantics.

A single authoritative schema lets us:

- publish consistent API docs,
- generate typed clients from one contract,
- enforce contract diffs in CI before release.

## Alternatives

- A: OpenAPI-first contract with generated clients.
- B: Handwritten client libraries per consumer stack.
- C: Human-readable docs with ad-hoc integration code.

## Decision Framework

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| **A** | **10** | **10** | **8** | **9** | **9.40** |
| B | 5 | 6 | 5 | 4 | 5.25 |
| C | 4 | 4 | 8 | 2 | 4.80 |

## Decision

Choose option A.

Implementation commitments:

- Generate and publish OpenAPI from service code.
- Keep SDK-facing `operationId` values stable, unique snake_case names and use
  semantic tags so generated client groupings remain ergonomic.
- Use `@hey-api/openapi-ts` for TypeScript generation and its generated fetch
  client surface for consumption.
- Use a thin `httr2` wrapper package for the R client when R SDK artifacts are
  required.
- Keep Python generated-client smoke verification via
  `openapi-python-client`.
- Keep custom request-body `$ref` entries resolvable within emitted component
  schemas so all generators receive a self-consistent contract.
- Treat schema changes as contract changes requiring review.

## Related Requirements

- [FR-0000](../requirements.md#fr-0000-file-transfer-control-plane-endpoints)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)

## Consequences

1. API changes must be model-first and reflected in OpenAPI before consumer updates.
2. CI should fail if schema generation or downstream client-generation checks break.
3. Multi-language consumers align on one contract artifact, reducing integration
   regressions and support overhead.

## Changelog

- 2026-03-05: Added stable SDK-facing `operationId`/tag rules and explicit
  component-schema requirements for custom request bodies.
- 2026-02-12: Added Python generated-client smoke verification commitment
  (`openapi-python-client`) and updated metadata.
- 2026-02-11: Expanded ADR with explicit generation commitments and stronger
  multi-language contract rationale.
- 2026-02-11: Initial ADR accepted.
