---
ADR: 0003
Title: API documentation site uses MkDocs Material and Scalar API Reference
Status: Accepted
Version: 1.1
Date: 2026-02-11
Related:
  - "[ADR-0002: Treat OpenAPI as the contract and generate client SDKs from it](./ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[SPEC-0004: CI/CD and documentation automation](../spec/SPEC-0004-ci-cd-and-docs.md)"
References:
  - "[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)"
  - "[Scalar documentation](https://docs.scalar.com/)"
  - "[scalar-fastapi package](https://pypi.org/project/scalar-fastapi/)"
  - "[FastAPI docs URL configuration](https://fastapi.tiangolo.com/tutorial/metadata/)"
---

## Summary

Use Material for MkDocs as the docs-as-code site and embed Scalar for interactive
OpenAPI browsing. Publish docs automatically from CI on merge/release flows.

## Context

The project requires:

- maintainable architecture documentation in-repo,
- modern interactive API reference backed by OpenAPI,
- automated publishing with minimal manual operations.

A docs stack is needed that remains lightweight for a service repo while still producing
high-quality API reference UX for developers integrating from different client stacks.

## Alternatives

- A: MkDocs Material + Scalar API reference (self-hosted docs site).
- B: Docusaurus + ReDoc integration.
- C: Managed vendor portal (for example Redocly SaaS).

## Decision Framework

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| **A** | **9** | **9** | **10** | **9** | **9.25** |
| B | 7 | 8 | 7 | 8 | 7.40 |
| C | 8 | 8 | 6 | 8 | 7.50 |

## Decision

Choose option A.

Implementation commitments:

- Render architecture and operational docs via MkDocs Material.
- Provide Scalar-based OpenAPI reference pages from generated schema.
- Publish docs through GitHub Actions to static hosting.

Known caveat:

- Scalar/FastAPI integrations can change quickly; keep FastAPI Swagger UI/ReDoc enabled
  as a resilience fallback during integration or release issues.

## Related Requirements

- [NFR-0001](../requirements.md#nfr-0001-documentation-automation)
- [IR-FT-003](../requirements.md#ir-ft-003-openapi-exposure-for-client-generation)

## Consequences

1. Documentation quality and API usability improve because architecture and contract docs
   are published together.
2. Build and publish pipelines become part of the release-critical path.
3. The team must maintain generated OpenAPI artifacts and docs navigation as the API
   evolves.

## Changelog

- 2026-02-11: Restored detailed decision context, caveats, and implementation
  commitments; removed template instruction prose.
- 2026-02-11: Initial ADR accepted.
