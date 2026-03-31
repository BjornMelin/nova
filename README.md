# Nova

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-control%20plane-009688?logo=fastapi&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-serverless-FF9900?logo=amazonaws&logoColor=white)
![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white)

Nova is a serverless file transfer and export orchestration platform.

At a product level, Nova gives browser, Dash, Python, TypeScript, and R clients a typed control plane for secure direct-to-S3 uploads, multipart transfer flows, presigned downloads, and durable export workflows.

At an engineering level, this repository is the canonical monorepo for the Nova runtime, SDKs, contracts, release automation, and AWS infrastructure. The active platform shape is a FastAPI control plane running on AWS Lambda behind API Gateway REST API and WAF, with S3, DynamoDB, and Step Functions providing the durable substrate.

## Status

- Current repo state: canonical serverless baseline
- Runtime style: regional API Gateway REST API + WAF + Lambda + Step Functions
- Auth model: bearer JWT only
- Primary IaC surface: `infra/nova_cdk`
- Python support: 3.11+
- Recommended local Python: 3.13
- License: proprietary / internal unless separately licensed

## What Nova does

Nova is intentionally a control plane, not the bulk data plane.

Clients upload and download data directly against AWS storage primitives using Nova-issued contracts and presigned URLs. Nova focuses on coordination, policy, identity, idempotency, export orchestration, release provenance, and downstream integration stability.

### Core capabilities

- Presigned direct upload initiation for single-part and multipart flows
- Multipart part signing, upload introspection, completion, and abort
- Presigned download issuance
- Durable export workflow creation, status tracking, listing, and optional cancellation
- Typed OpenAPI contract with generated TypeScript and Python SDKs, plus a thin R client
- Repo-owned release, deploy, and post-deploy validation workflows
- Published deploy-output provenance for runtime URL authority and release identity

### Hard-cut design laws

These are intentional platform constraints, not temporary migrations:

- Bearer JWT only
- Explicit `/v1/exports` workflows instead of generic jobs
- DynamoDB-backed idempotency and workflow state
- `infra/nova_cdk` as the only active infrastructure implementation path
- One SDK package per language
- Direct-to-S3 transfer model with Nova as the control plane

### Explicitly retired assumptions

Do not treat any of the following as current platform behavior:

- session auth or same-origin auth contracts
- a dedicated auth service
- generic jobs APIs
- Redis-backed correctness paths
- ECS/Fargate runtime stacks
- CloudFront as compensating API ingress
- split file/auth SDK packages
- free-text runtime base URL configuration when `deploy-output.json` is available

## Architecture at a glance

```text
Browser / Dash / TS / Python / R clients
                |
     API Gateway REST API + WAF
                |
      Lambda (FastAPI via Mangum)
                |
       DynamoDB + S3 + Step Functions
                |
   Lambda workflow handlers and SDK generation
```

### Current platform responsibilities

Nova is responsible for:

- issuing upload intents and multipart part URLs
- completing and aborting uploads
- issuing download URLs
- creating and tracking export workflows
- exposing typed operational and capability endpoints
- publishing stable contract and release artifacts for downstream consumers

Nova is not responsible for:

- acting as the byte stream for large uploads or downloads
- hosting a browser session-auth surface
- serving a generic background-jobs API
- preserving legacy ECS-era deployment patterns

## Primary API surface

### Transfers

- `POST /v1/transfers/uploads/initiate`
- `POST /v1/transfers/uploads/sign-parts`
- `POST /v1/transfers/uploads/introspect`
- `POST /v1/transfers/uploads/complete`
- `POST /v1/transfers/uploads/abort`
- `POST /v1/transfers/downloads/presign`

### Exports

- `POST /v1/exports`
- `GET /v1/exports`
- `GET /v1/exports/{export_id}`
- `POST /v1/exports/{export_id}/cancel`

### Platform and ops

- `GET /v1/capabilities`
- `POST /v1/resources/plan`
- `GET /v1/releases/info`
- `GET /v1/health/live`
- `GET /v1/health/ready`
- `GET /metrics/summary`

## Repository map

| Path | Role | Notes |
| --- | --- | --- |
| `packages/nova_file_api` | Public FastAPI control plane | Canonical API and Lambda entrypoint |
| `packages/nova_workflows` | Export workflow handlers | Step Functions task and workflow logic |
| `packages/nova_runtime_support` | Shared runtime helpers | Request context, auth claims, logging, OpenAPI helpers |
| `packages/nova_dash_bridge` | Downstream framework bridge | Dash, Flask, and FastAPI integration helpers |
| `packages/nova_sdk_ts` | Generated TypeScript SDK | Published as `@nova/sdk` with subpath exports |
| `packages/nova_sdk_py` | Generated Python SDK | Published as `nova-sdk-py` |
| `packages/nova_sdk_r` | Thin R SDK | `httr2`-style client package |
| `packages/contracts` | Contract artifacts and conformance fixtures | OpenAPI, runtime contract fixtures, TS conformance package |
| `infra/nova_cdk` | Canonical AWS CDK app | Runtime deployment surface |
| `scripts/release` | Release and generation automation | Versions, SDK generation, deploy artifact handling |
| `scripts/contracts` | Contract export helpers | OpenAPI export and related checks |
| `tests/infra` | Infra and workflow contract tests | Docs authority, IAM, deploy-output, runtime stack validation |
| `docs/` | Active docs, runbooks, ADRs, specs, release artifacts | Canonical authority is routed from `docs/README.md` |
| `.github/workflows/` | CI, release, deploy, validation | GitHub-driven delivery and promotion model |

## SDKs and downstream consumers

Nova currently ships or maintains:

- TypeScript SDK: `@nova/sdk`
- Python SDK: `nova-sdk-py`
- R SDK: `nova`
- Dash/Flask/FastAPI bridge helpers in `nova-dash-bridge`

Downstream guidance and examples live in:

- `docs/clients/README.md`
- `docs/clients/post-deploy-validation-integration-guide.md`
- `docs/clients/examples/workflows/`

## Start here

Read in this order if you are new to the repo:

1. `AGENTS.md`
2. `docs/README.md`
3. `docs/architecture/README.md`
4. `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
5. `docs/runbooks/README.md`
6. `docs/standards/repository-engineering-standards.md`

## Local development

### Prerequisites

- Python 3.13 recommended, 3.11+ supported
- `uv`
- Node 24 LTS if you touch TypeScript SDK or TS conformance
- R if you touch `packages/nova_sdk_r`
- AWS credentials and CDK bootstrap only if you are working on infrastructure or deploy flows

### Bootstrap

```bash
uv sync --locked --all-packages --all-extras --dev
npm ci
uv run pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push
```

`npm ci` is only required when you are touching the TypeScript SDK, TypeScript conformance package, or generator/conformance flows that depend on the checked-in npm workspace.

### Run the API locally

```bash
uv run fastapi dev packages/nova_file_api/src/nova_file_api/main.py
```

### Core repo verification

```bash
uv lock --check
uv run ruff check .
uv run ruff check . --select I
uv run ruff format . --check
uv run ty check --force-exclude --error-on-warning packages scripts
uv run mypy
uv run pytest -q -m runtime_gate
uv run pytest -q -m "not runtime_gate and not generated_smoke"
uv run pytest -q -m generated_smoke
```

### Contract and generator verification

```bash
uv run python scripts/contracts/export_openapi.py --check
uv run python scripts/release/generate_runtime_config_contract.py --check
uv run python scripts/release/generate_clients.py --check
uv run python scripts/release/generate_python_clients.py --check
```

### TypeScript SDK and conformance verification

```bash
npm run build:typescript:sdk-graph
npm run -w @nova/sdk typecheck
npm run -w @nova/sdk build
npm run -w @nova/contracts-ts-conformance typecheck
npm run -w @nova/contracts-ts-conformance verify
uv run pytest -q scripts/release/tests/test_typescript_sdk_contracts.py
uv run python scripts/conformance/check_typescript_module_policy.py
```

### Infrastructure and workflow contract verification

```bash
bash scripts/checks/run_infra_contracts.sh
npx aws-cdk@2.1107.0 synth --app "uv run --package nova-cdk python infra/nova_cdk/app.py" \
  -c account=111111111111 \
  -c region=us-west-2 \
  -c api_domain_name=api.dev.example.com \
  -c hosted_zone_id=Z1234567890EXAMPLE \
  -c hosted_zone_name=example.com \
  -c api_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c api_lambda_artifact_key=runtime/nova-file-api/example/example/nova-file-api-lambda.zip \
  -c api_lambda_artifact_sha256=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000 \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
```

## Release and deployment model

Nova uses a GitHub workflow-driven release and deploy pipeline.

### High-level flow

1. `Nova Release Plan`
2. `Nova Release Apply`
3. `Verify Release Signature`
4. `Deploy Runtime`
5. `Publish Packages`
6. `Promote Prod`
7. `Post Deploy Validate` when revalidation is needed

### Important release concepts

- Release automation builds and publishes the API Lambda artifact
- CDK consumes explicit artifact coordinates instead of rebuilding the API package locally
- Runtime deployment publishes `deploy-output.json` and `deploy-output.sha256`
- Post-deploy validation binds to that deploy-output artifact instead of manually supplied base URLs
- Staged package publication and prod promotion are digest-gated

For operational details, start with:

- `docs/runbooks/release/README.md`
- `docs/runbooks/release/release-runbook.md`
- `infra/nova_cdk/README.md`

## Documentation authority

Nova intentionally keeps a small active authority set and archives historical material instead of mixing waves of guidance.

### Active documentation routers

- `docs/README.md`
- `docs/architecture/README.md`
- `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `docs/overview/ACTIVE-DOCS-INDEX.md`
- `docs/runbooks/README.md`
- `docs/contracts/README.md`
- `docs/clients/README.md`
- `docs/release/README.md`

### Historical material

The following are useful for traceability only and must not be treated as the active implementation baseline:

- `docs/history/**`
- `docs/architecture/adr/superseded/**`
- `docs/architecture/spec/superseded/**`
- older ECS-era, auth-service, split-SDK, or generic-jobs assumptions

## Working with Codex and other agents

Repo-wide agent guidance lives in `AGENTS.md`.

Use `AGENTS.md` first, then the docs routers above, then the domain-specific package README or runbook for the area you are changing. If a task repeatedly needs more local guidance, prefer adding a narrow package-level `AGENTS.md` close to that subtree instead of expanding the root file with low-signal detail.

## Contributing rules

- Treat OpenAPI, generator inputs, and generator scripts as the source of truth for generated SDK output
- Prefer fixing source, templates, or generation code instead of hand-editing generated artifacts
- Update docs, tests, and contracts in the same branch when behavior changes
- Keep active docs aligned with the active package graph and workflow surface
- Do not reintroduce retired platform assumptions into code, docs, CI, or prompts

## Further reading

- Architecture authority: `docs/architecture/README.md`
- Program and current-state map: `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
- Engineering standards: `docs/standards/repository-engineering-standards.md`
- Release operations: `docs/runbooks/release/release-runbook.md`
- Serverless operations: `docs/runbooks/RUNBOOK-SERVERLESS-OPERATIONS.md`
- Runtime infrastructure: `infra/nova_cdk/README.md`
