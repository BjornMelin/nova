---
Spec: 0004
Title: CI/CD and Documentation Automation
Status: Active
Version: 1.2
Date: 2026-02-12
Related:
  - "[ADR-0002: OpenAPI as contract and SDK generation](../adr/ADR-0002-openapi-as-contract-and-sdk-generation.md)"
  - "[ADR-0003: MkDocs Material + Scalar docs stack](../adr/ADR-0003-api-docs-site-mkdocs-material-plus-scalar.md)"
  - "[SPEC-0000: HTTP API contract](./SPEC-0000-http-api-contract.md)"
References:
  - "[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)"
  - "[Scalar docs](https://docs.scalar.com/)"
  - "[GitHub Actions](https://docs.github.com/actions)"
  - "[OpenAPI Generator](https://openapi-generator.tech/)"
---

## 1. Required quality gates

Every pull request MUST pass:

- `source .venv/bin/activate && uv run ruff check .`
- `source .venv/bin/activate && uv run ruff check . --select I`
- `source .venv/bin/activate && uv run mypy`
- `source .venv/bin/activate && uv run pytest -q`
- container image build validation

## 2. Build and deploy pipeline

On pull request:

- run quality gates
- build image artifact
- generate OpenAPI artifact and verify schema validity

On merge to main:

- publish image to registry
- deploy to development environment via container-craft workflow
- publish docs preview or latest docs

On release tag:

- deploy to production
- publish versioned docs and API reference

## 3. Documentation pipeline

Docs stack:

- MkDocs Material for architecture and operational docs
- Scalar API reference rendered from OpenAPI schema

The docs pipeline MUST fail if:

- OpenAPI generation fails,
- docs build fails,
- broken internal links are detected in ADR/SPEC navigation.

When runtime behavior or error semantics change, the same pull request MUST
include updates to:

- `README.md`
- `PRD.md`
- affected `requirements.md`, `SPEC`, `ADR`, and `PLAN`/`SUBPLAN` docs

The PR template must include a completed checklist item referencing this rule (for
example: `Documentation updated: README.md, PRD.md, affected requirements.md /
SPEC / ADR / PLAN/SUBPLAN`) whenever behavior changes.

## 4. Client generation workflow

- TypeScript types/client: `openapi-typescript` + `openapi-fetch`
- R client: OpenAPI Generator (`r` generator) when release process requires it
- Python smoke validation: `openapi-python-client` generation + compile check
  from runtime OpenAPI output

Client generation SHOULD run as a verification step on contract changes.
The runtime repository keeps this via
`packages/nova_file_api/tests/test_generated_client_smoke.py`.

## 5. Traceability

- [FR-0008](../requirements.md#fr-0008-openapi-contract-ownership)
- [NFR-0004](../requirements.md#nfr-0004-cicd-and-quality-gates)
