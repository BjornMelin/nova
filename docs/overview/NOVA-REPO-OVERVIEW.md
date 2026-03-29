# Nova repository overview

Status: Active orientation doc
Last reviewed: 2026-03-28

## One-sentence summary

Nova is a serverless transfer and export-workflow control-plane monorepo with
bearer-only auth, DynamoDB-backed idempotency, unified SDK packages, and
`infra/nova_cdk` as the active infrastructure surface.

## Core components

- `packages/nova_file_api`
- `packages/nova_workflows`
- `packages/nova_runtime_support`
- `packages/nova_dash_bridge`
- `packages/nova_sdk_ts`
- `packages/nova_sdk_py`
- `packages/nova_sdk_r`
- `infra/nova_cdk`

## Where to read next

- `IMPLEMENTATION-STATUS-MATRIX.md`
- `ACTIVE-DOCS-INDEX.md`
- `../plan/GREENFIELD-WAVE-2-EXECUTION.md`
- `../architecture/README.md`
- `../runbooks/README.md`

## Canonical authority chain

- `../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `../architecture/requirements-wave-2.md`
- `../architecture/adr/ADR-0033-canonical-serverless-platform.md` through `../architecture/adr/ADR-0038-docs-authority-reset.md`
- `../architecture/spec/SPEC-0027-public-api-v2.md` through `../architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
