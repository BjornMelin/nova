---
ADR: 0000
Title: Implement the File Transfer API as a FastAPI service
Status: Accepted
Version: 1.1
Date: 2026-02-11
Related:
  - "[ADR-0002: Treat OpenAPI as the contract and generate client SDKs from it](./ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0027: Public API v2](../spec/SPEC-0027-public-api-v2.md)"
References:
  - "[FastAPI deployment concepts](https://fastapi.tiangolo.com/deployment/concepts/)"
  - "[FastAPI metadata and docs URLs](https://fastapi.tiangolo.com/tutorial/metadata/)"
  - "[FastAPI OpenAPI URL configuration](https://fastapi.tiangolo.com/tutorial/metadata/#openapi-url)"
---

## Summary

Build the File Transfer control-plane API as a FastAPI application using Pydantic v2
models. This gives strict request/response typing, native OpenAPI generation, and a
production-ready ASGI runtime with minimal custom framework glue.

## Context

The service must orchestrate S3 presigned upload/download workflows while staying
portable across Dash, R Shiny, and Next.js consumers. The key constraints are:

- Contract-first API design with durable OpenAPI output for docs and SDK generation.
- Low operational complexity in ECS/Fargate deployment.
- High implementation velocity without sacrificing validation correctness.
- Strong alignment with Python typing and structured error handling patterns.

Flask-based and Django-based options were considered, but both would require more
manual schema wiring and extra glue to keep docs, code, and generated clients aligned.

## Alternatives

- A: FastAPI + Pydantic v2 for API routing, validation, and OpenAPI generation.
- B: Flask + Marshmallow + manual OpenAPI tooling.
- C: Django REST Framework + serializers/viewsets.

## Decision Framework

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| **A** | **10** | **9** | **9** | **9** | **9.35** |
| B | 7 | 7 | 6 | 7 | 6.75 |
| C | 7 | 7 | 5 | 7 | 6.50 |

## Decision

Choose option A: implement the service in FastAPI with Pydantic v2 models as the
canonical contract layer.

Specific decision points:

- FastAPI-generated OpenAPI (`/openapi.json`) is treated as a first-class artifact.
- Built-in docs endpoints (`/docs`, `/redoc`) remain available unless explicitly
  disabled by environment policy.
- Validation and serialization stay model-driven to avoid schema drift.

## Related Requirements

- [FR-0000](../requirements.md#fr-0000-file-transfer-control-plane-endpoints)
- [FR-0009](../requirements.md#fr-0009-s3-multipart-correctness-and-acceleration-compatibility)
- [FR-0003](../requirements.md#fr-0003-key-generation-and-scope-enforcement)
- [FR-0005](../requirements.md#fr-0005-authentication-and-authorization)
- [FR-0007](../requirements.md#fr-0007-observability-and-analytics)
- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)

## Consequences

1. OpenAPI and runtime validation are produced from the same model definitions, reducing
   contract drift.
2. Team conventions must stay strict on typing and Pydantic model usage to preserve the
   architectural benefit.
3. FastAPI version changes can affect schema generation details; upgrades should include
   contract diff checks in CI.

## Changelog

- 2026-02-11: Expanded and refined ADR with project-specific rationale, richer
  traceability, and normalized links.
- 2026-02-11: Initial ADR accepted.
