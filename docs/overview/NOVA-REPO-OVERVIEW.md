# Nova repository overview

Status: Active orientation doc
Last reviewed: 2026-04-07

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
- `../architecture/README.md`
- `../runbooks/README.md`

## Canonical authority chain

- `../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `../architecture/requirements.md`
- `../architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `../architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `../architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `../architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `../architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `../architecture/adr/ADR-0038-docs-authority-reset.md`
- `../architecture/adr/ADR-0039-lambda-runtime-bootstrap-and-runtime-container.md`
- `../architecture/spec/SPEC-0027-public-api-v2.md`
- `../architecture/spec/SPEC-0028-export-workflow-state-machine.md`
- `../architecture/spec/SPEC-0029-platform-serverless.md`
- `../architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `../architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
