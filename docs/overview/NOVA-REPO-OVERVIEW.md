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
- `CANONICAL-TARGET-2026-04.md`
- `../architecture/README.md`
- `../runbooks/README.md`
