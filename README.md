# nova

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-0.135.2%2B-009688?logo=fastapi&logoColor=white) ![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white)

Nova is a serverless file-transfer and export control-plane monorepo.

## Start here

Read in this order:

1. `AGENTS.md`
2. `docs/README.md`
3. `docs/architecture/README.md`
4. `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
5. `docs/runbooks/README.md`

## Canonical system

The active repo baseline is the final wave-2 system:

- public FastAPI control plane in `packages/nova_file_api`
- workflow orchestration in `packages/nova_workflows`
- shared runtime helpers in `packages/nova_runtime_support`
- async-first Dash/browser bridge in `packages/nova_dash_bridge`
- one SDK package per language: `packages/nova_sdk_ts`, `packages/nova_sdk_py`, `packages/nova_sdk_r`
- canonical infrastructure in `infra/nova_cdk`
- bearer JWT only
- explicit export workflows, not generic jobs
- DynamoDB + S3 + Step Functions as the durable runtime substrate

## Package map

- `packages/nova_file_api`
- `packages/nova_workflows`
- `packages/nova_runtime_support`
- `packages/nova_dash_bridge`
- `packages/nova_sdk_ts`
- `packages/nova_sdk_py`
- `packages/nova_sdk_r`
- `infra/nova_cdk`

## Release and validation

- Package release workflows live under `.github/workflows/`.
- Machine-stable release artifacts live under `docs/release/`.
- Serverless infrastructure guidance starts in `infra/nova_cdk/README.md`.

## Documentation rules

- Use `docs/architecture/README.md` as the architecture router.
- Use `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md` for the active truth model.
- Treat `docs/history/**` and `docs/architecture/*/superseded/**` as traceability only.
