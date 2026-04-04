# AGENTS.md

## Purpose

Durable, repo-wide rules for AI coding agents in Nova. Practical and tied to
this repository. Narrower rules belong next to the package they govern.

**Session entrypoint:** Continue with `docs/README.md` (router), then the
ordered list below—not `docs/history/**` or `docs/architecture/*/superseded/**`
(traceability only; not authority).

## What Nova is

Typed control plane for direct-to-S3 uploads/downloads, multipart flows, and
durable export workflows; OpenAPI + generated SDKs (TS, Python, R). Nova is not
the bulk data plane. Product and API detail: `README.md`.

## Read first

1. `docs/README.md`
2. `docs/architecture/README.md`
3. `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
4. `README.md`
5. `docs/standards/repository-engineering-standards.md`
6. `docs/runbooks/README.md` — if deploy, release, operations, or AWS
7. `docs/clients/README.md` — if SDKs or downstream integration examples

## Repo truth and hard bans

**Current implementation (treat as true):**

- Public API: transfer routes under `/v1/transfers/*`, export routes under
  `/v1/exports*`, supporting capability/ops routes under `/v1/*`, and
  `/metrics/summary`. Auth:
  bearer JWT only, in-process.
- Transfer control plane: initiate responses include additive policy/session
  hints for browser clients, upload-session state is persisted in DynamoDB,
  transfer quota counters are persisted in DynamoDB, AppConfig can narrow the
  effective transfer policy with environment-safe fallback, selective transfer
  acceleration and checksum requirements are policy-controlled, and
  `/v1/capabilities/transfers` exposes the effective transfer policy envelope.
- Exports: `/v1/exports`. Idempotency and workflow state: DynamoDB. Moderate
  export copies stay inline; larger server-side copies use an internal
  SQS-backed worker lane with durable part state in DynamoDB and Step Functions
  Standard polling/finalization.
- Export cancellation persists caller intent and stops the active Step
  Functions execution when one is running; queued copy workers must check the
  export record before copying parts.
- API runtime: FastAPI in `packages/nova_file_api` (repo Lambda entrypoint).
- Workflows: Step Functions + `packages/nova_workflows` task handlers.
- Multipart cleanup: `packages/nova_workflows` also owns the scheduled
  reconciliation handler for expired sessions and orphaned multipart uploads.
- Browser/Dash upload helpers: `packages/nova_dash_bridge` is browser-only; the
  consumer app owns token acquisition and renders the bearer header DOM node
  that the uploader reads.
- IaC: `infra/nova_cdk` only. SDKs: one package per language (TS, Py, R).
- Deployed base URL and release provenance: `deploy-output.json` (not manual
  or free-text config when that artifact exists).

**Never reintroduce** (code, docs, CI, prompts, reviews):

- Session / same-origin auth or a dedicated auth service
- Generic jobs APIs, internal callback routes, or non-export workflow semantics
  where explicit `/v1/exports` is the model
- Redis-backed correctness or idempotency
- ECS/Fargate as primary runtime; CloudFront as compensating public API ingress
- Lambda Web Adapter or uvicorn-in-Lambda for the public API runtime
- Split SDK packages (e.g. file/auth split), or package-root barrel exports on
  `@nova/sdk`
- Hand-editing generated SDKs or generated docs as the primary fix (fix
  OpenAPI, templates, or generators; see **Commands** for `--check` gates)

## Repo map

| Path | Role |
| --- | --- |
| `packages/nova_file_api` | API, auth, transfer + export routes, Lambda entry |
| `packages/nova_workflows` | Step Functions tasks, workflow logic |
| `packages/nova_runtime_support` | Shared runtime helpers |
| `packages/nova_dash_bridge` | Browser-only Dash uploader assets and bearer-header helpers |
| `packages/contracts` | OpenAPI artifacts, fixtures, TS conformance assets |
| `packages/nova_sdk_{ts,py,r}` | Generated public clients |
| `infra/nova_cdk` | Canonical CDK app |
| `apps/nova_workflows_tasks` | Workflow task Lambda image build context |
| `scripts/contracts` | Contract export and checks |
| `scripts/release` | Release generation, packaging, deploy-output helpers |
| `tests/infra` | Infra, docs-authority, deployment contract tests |
| `.github/workflows` | CI, release, publish, deploy, post-deploy validation |

## Working rules

1. **Plan first** when cross-package, architecture-affecting, infra/release,
   contract or SDK generation, or ambiguous enough that blind edits are risky.
   Narrow fixes: proceed.

2. **Smallest coherent change** — buildable and testable; preserve public
   behavior unless a breaking change is explicit; behavior changes ship with
   tests in the same branch.

3. **Fix sources** — wrong generated output → OpenAPI, generator/templates,
   runtime, infra, or release metadata first. Manual edits only where a file
   is intentionally hand-maintained.

4. **Docs** — If behavior, contracts, workflows, commands, inputs, layout, or
   operator steps change, update the same branch. Use `docs/README.md` and
   `docs/overview/ACTIVE-DOCS-INDEX.md` to find surfaces; always reassess
   `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`, root `README.md`, and
   `infra/nova_cdk/README.md` for platform shifts. Update `AGENTS.md` when
   global agent truth changes. In committed docs and code comments, write in
   durable operator/architecture language; do not copy temporary plan labels
   such as "phase", "wave", or similar working-note framing unless they are
   part of an active repo authority document.

5. **Toolchain** — `uv` for Python env and commands; Python 3.11 syntax;
   Ruff, mypy, ty, pytest as configured. **`npm ci` only** when touching the TS
   workspace, TS SDK output, or TS conformance. No overlapping toolchains
   without a strong repo-specific reason.

## Release sessions

- If the task is release, deploy, runtime cutover, or post-deploy validation,
  read these in order before editing:
  1. `docs/runbooks/README.md`
  2. `docs/runbooks/release/release-runbook.md`
  3. `infra/nova_cdk/README.md`
  4. `docs/contracts/deploy-output-authority-v2.schema.json`
- Treat the supported release path as:
  1. land repo-side fixes on `main`
  2. generate and merge a human-authored `release/RELEASE-PREP.json` plus
     `release/RELEASE-VERSION-MANIFEST.md` refresh when release metadata or
     releasable unit versions changed
  3. let `nova-release-control-plane` execute post-merge publish and deploy
- Treat `deploy-output.json` as the runtime authority for deployed URL and
  release identity.
- Do not bypass the release-prep artifact contract, rebuild prod outside the
  stored release execution manifest, or reintroduce GitHub-hosted release
  executors as active paths.

## Commands

Run from repository root unless the task needs otherwise.

### Bootstrap

```bash
uv sync --locked --all-packages --all-extras --dev
# npm ci  — only if TS workspace / TS SDK / TS conformance is in scope
```

### Python verification

```bash
uv lock --check
uv run ruff check . && uv run ruff check . --select I && uv run ruff format . --check
uv run ty check --force-exclude --error-on-warning packages scripts
uv run mypy
uv run pytest -q -m runtime_gate
uv run pytest -q -m "not runtime_gate and not generated_smoke"
uv run pytest -q -m generated_smoke
```

### Contracts and generators

```bash
uv run python scripts/contracts/export_openapi.py --check
uv run python scripts/release/generate_runtime_config_contract.py --check
uv run python scripts/release/generate_clients.py --check
uv run python scripts/release/generate_python_clients.py --check
```

### TypeScript SDK and conformance (after `npm ci` when needed)

```bash
npm run build:typescript:sdk-graph
npm run -w @nova/sdk typecheck && npm run -w @nova/sdk build
npm run -w @nova/contracts-ts-conformance typecheck
npm run -w @nova/contracts-ts-conformance verify
uv run pytest -q scripts/release/tests/test_typescript_sdk_contracts.py
uv run python scripts/conformance/check_typescript_module_policy.py
```

### Infra

```bash
bash scripts/checks/run_infra_contracts.sh
```

Repo-native CDK synth example:

```bash
npx aws-cdk@2.1107.0 synth --app "uv run --package nova-cdk python infra/nova_cdk/app.py" \
  -c account=111111111111 \
  -c region=us-west-2 \
  -c api_domain_name=api.dev.example.com \
  -c hosted_zone_id=Z1234567890EXAMPLE \
  -c hosted_zone_name=example.com \
  -c api_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c api_lambda_artifact_key=runtime/nova-file-api/example/example/nova-file-api-lambda.zip \
  -c api_lambda_artifact_sha256=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
  -c workflow_lambda_artifact_bucket=nova-ci-artifacts-111111111111-us-east-1 \
  -c workflow_lambda_artifact_key=runtime/nova-workflows/example/example/nova-workflows-lambda.zip \
  -c workflow_lambda_artifact_sha256=fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210 \
  -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000 \
  -c jwt_issuer=https://issuer.example.com/ \
  -c jwt_audience=api://nova \
  -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json
```

For production context values and additional CDK guidance, see
`infra/nova_cdk/README.md`.

## Task Router

Fenced blocks mirror **Commands** for agent gate runners; keep them aligned when
commands change.

### Bootstrap

```bash
uv sync --locked --all-packages --all-extras --dev
# npm ci  — only if TS workspace / TS SDK / TS conformance is in scope
```

### Python verification

```bash
uv lock --check
uv run ruff check . && uv run ruff check . --select I && uv run ruff format . --check
uv run ty check --force-exclude --error-on-warning packages scripts
uv run mypy
uv run pytest -q -m runtime_gate
uv run pytest -q -m "not runtime_gate and not generated_smoke"
uv run pytest -q -m generated_smoke
```

### Contracts and generators

```bash
uv run python scripts/contracts/export_openapi.py --check
uv run python scripts/release/generate_runtime_config_contract.py --check
uv run python scripts/release/generate_clients.py --check
uv run python scripts/release/generate_python_clients.py --check
```

### TypeScript SDK and conformance (after `npm ci` when needed)

```bash
npm run build:typescript:sdk-graph
npm run -w @nova/sdk typecheck && npm run -w @nova/sdk build
npm run -w @nova/contracts-ts-conformance typecheck
npm run -w @nova/contracts-ts-conformance verify
uv run pytest -q scripts/release/tests/test_typescript_sdk_contracts.py
uv run python scripts/conformance/check_typescript_module_policy.py
```

### Infra

```bash
bash scripts/checks/run_infra_contracts.sh
```

## Task routing

| Topic | Start here |
| --- | --- |
| Architecture / current truth | `docs/architecture/README.md`, `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`, `docs/overview/ACTIVE-DOCS-INDEX.md` |
| Public API / runtime | `packages/nova_file_api`, `packages/nova_runtime_support`, `packages/contracts/openapi/nova-file-api.openapi.json`, SPEC-0027, SPEC-0029 |
| Workflows | `packages/nova_workflows`, SPEC-0028, `infra/nova_cdk/src/nova_cdk/runtime_stack.py` |
| SDKs / clients | `packages/contracts`, `packages/nova_sdk_ts`, `packages/nova_sdk_py`, `packages/nova_sdk_r`, `scripts/release/generate_clients.py`, `scripts/release/generate_python_clients.py`, `docs/clients/README.md` |
| Release / deploy automation | `.github/workflows/`, `docs/runbooks/release/`, `docs/runbooks/release/release-runbook.md`, `docs/contracts/deploy-output-authority-v2.schema.json`, `docs/contracts/workflow-post-deploy-validate.schema.json`, `infra/nova_cdk/README.md` |

Specs live under `docs/architecture/spec/` (e.g. `SPEC-0027-public-api-v2.md`).

**Public SDK surface:** OpenAPI is authority. Do not add internal-only
operations, bespoke transport layers, or bundled validation helpers to the
generated TS SDK. `generate_clients.py --check` and
`generate_python_clients.py --check` are deterministic gates.

## Review and done

- **Review:** Correctness, security, contract stability, release integrity, and
  operator truth over style. High priority: auth, authorization, CORS,
  deploy-output provenance, execute-api posture, reserved concurrency, release
  digest regressions. **P1:** missing tests or docs for changed behavior;
  wrong paths, stale architecture, or broken commands in active docs; generator
  or contract drift when sources changed but outputs did not. Skip nitpicking
  what Ruff, ty, mypy, or existing contract tests already enforce unless that
  gate is missing or bypassed.

- **Done:** Matches repo truth above; verification run or explicitly deferred;
  tests updated for behavior changes; contracts and generated outputs updated
  when sources changed; no retired assumption reintroduced; active docs remain
  truthful.
