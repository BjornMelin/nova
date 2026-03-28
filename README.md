# nova

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-0.135.2%2B-009688?logo=fastapi&logoColor=white) ![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white)

Nova is a file-transfer and export control-plane monorepo.

This docs-alignment pack is intentionally honest about state:

- the **current implemented baseline** is still the pre-wave-2 repository shape
  (ECS/SQS/Redis/generic-jobs/auth-service era)
- the **approved target** is the wave-2 hard cut documented under
  `docs/architecture/adr/ADR-0033` through `ADR-0038` and
  `docs/architecture/spec/SPEC-0027` through `SPEC-0031`

Use this README as orientation only. It does **not** replace the architecture
authority docs.

## Start here

Read in this order:

1. `AGENTS.md`
2. `docs/README.md`
3. `docs/architecture/README.md`
4. `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
5. `docs/plan/GREENFIELD-WAVE-2-EXECUTION.md` when you are executing the
   wave-2 implementation branches

## Current implemented baseline

The current repository is already partway through the wave-2 hard cut. The
implemented baseline today includes:

- public transfer APIs plus explicit export workflows
- bearer JWT only, verified in-process in the main API
- DynamoDB-backed idempotency with explicit expiration filtering
- HTTP API + Lambda Web Adapter + Step Functions Standard as the canonical
  newly landed runtime path
- legacy ECS/Fargate + ALB + SQS worker assets retained only as non-canonical
  migration leftovers
- unified SDK package directories for TypeScript, Python, and R

Use the current implemented runbooks under `docs/runbooks/provisioning/` and
`docs/runbooks/release/` for live operations until the target migration lands.

## Approved target after wave 2

The approved hard-cut target is:

- bearer JWT only
- no dedicated auth service
- explicit export workflow resources instead of generic jobs
- DynamoDB instead of Redis in the canonical runtime
- API Gateway HTTP API + Lambda Web Adapter + Step Functions Standard as the
  canonical AWS deployment shape
- one canonical SDK package per language
- a smaller, clearer active docs authority surface

Primary target-state references:

- `docs/overview/CANONICAL-TARGET-2026-04.md`
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `docs/architecture/adr/ADR-0034-eliminate-auth-service-and-session-auth.md`
- `docs/architecture/adr/ADR-0035-replace-generic-jobs-with-export-workflows.md`
- `docs/architecture/adr/ADR-0036-dynamodb-idempotency-no-redis.md`
- `docs/architecture/adr/ADR-0037-sdk-generation-consolidation.md`
- `docs/architecture/adr/ADR-0038-docs-authority-reset.md`
- `docs/plan/GREENFIELD-WAVE-2-EXECUTION.md`

## Package orientation

### Current baseline packages

The current repo layout includes:

- `packages/nova_file_api`
- `packages/nova_workflows`
- `packages/nova_dash_bridge`
- `packages/nova_runtime_support`
- `packages/nova_sdk_ts`
- `packages/nova_sdk_py`
- `packages/nova_sdk_r`
- `infra/nova_cdk`

### Target package layout

The approved target package map is:

- `packages/nova_file_api`
- `packages/nova_workflows`
- `packages/nova_runtime_support`
- `packages/nova_dash_bridge`
- `packages/nova_sdk_ts`
- `packages/nova_sdk_py`
- `packages/nova_sdk_r`
- `infra/nova_cdk`

See `docs/overview/CANONICAL-TARGET-2026-04.md` and
`docs/clients/CLIENT-SDK-CANONICAL-PACKAGES.md`.

## Documentation rules

- Use `docs/architecture/README.md` as the router for architecture authority.
- Use `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md` to avoid mixing current
  baseline facts with target-state decisions.
- Treat `docs/history/**` and `docs/architecture/*/superseded/**` as
  traceability-only.
