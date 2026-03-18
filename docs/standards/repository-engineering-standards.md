# Repository Engineering Standards

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-17

## Purpose

Capture durable repo engineering and operator rules that are too detailed for
`AGENTS.md` but should still guide fresh-context sessions.

## Reading Order for Fresh Sessions

1. `AGENTS.md`
2. `README.md`
3. `docs/README.md`
4. `docs/architecture/README.md`
5. `docs/overview/NOVA-REPO-OVERVIEW.md`
6. `docs/runbooks/README.md` when the task affects release or operations

## Authority Classification

Use these authority packs consistently:

- runtime API and route authority:
  - `requirements.md`
  - `ADR-0023`
  - `SPEC-0000`
  - `SPEC-0015`
  - `SPEC-0016`
- runtime topology and safety authority:
  - `ADR-0024`
  - `ADR-0025`
  - `ADR-0026`
  - `SPEC-0017`
  - `SPEC-0018`
  - `SPEC-0019`
  - `SPEC-0020`
- downstream validation authority:
  - `ADR-0027`
  - `ADR-0028`
  - `ADR-0029`
  - `SPEC-0021`
  - `SPEC-0022`
  - `SPEC-0023`
- adjacent deploy-governance authority:
  - `ADR-0015`
  - `ADR-0030`
  - `ADR-0031`
  - `ADR-0032`
  - `SPEC-0024`
  - `SPEC-0025`
  - `SPEC-0026`

## Workflow Mapping

Use the repo workflows as the enforcement map:

- `.github/workflows/ci.yml`
  - runtime reliability, baseline quality gates, required `ty` plus `mypy`
    compatibility backstop, canonical-route guard
- `.github/workflows/conformance-clients.yml`
  - OpenAPI export, generated SDK checks, TS/R conformance
- `.github/workflows/cfn-contract-validate.yml`
  - CloudFormation syntax/schema plus docs/infra contract checks

Repo-local enforcement complements CI:

- root `.pre-commit-config.yaml`
- `scripts/checks/run_quality_gates.sh`
- `scripts/checks/run_sdk_conformance.sh`
- `scripts/checks/run_infra_contracts.sh`
- `scripts/checks/run_docker_release_images.sh`
- `scripts/dev/install_hooks.sh`

`AGENTS.md` intentionally carries only the short execution subset. This file is
the canonical deep matrix.

## Generated TypeScript SDK Rules

- Generated TypeScript packages are `@nova/sdk-auth`, `@nova/sdk-file`, and the
  shared runtime/helper package `@nova/sdk-fetch`.
- Publicly supported imports remain subpath-only. Do not add package-root `"."`
  exports.
- Do not create `index.ts` files or re-export barrels.
- `types` surfaces stay curated; do not expose raw whole-spec aliases or
  internal-only worker models.
- Internal/admin operations marked with `x-nova-sdk-visibility: internal` stay
  excluded from generated SDK output.
- Generated TypeScript SDKs are validation-free. Do not add `zod`, validator
  packages, validator subpaths, or runtime request/response validation helpers.
- OpenAPI remains the only schema authority for SDK generation.
- Multi-media request bodies must preserve explicit generated `contentType`
  selection instead of collapsing to JSON-only behavior.
- Shared transport/runtime logic belongs in `@nova/sdk-fetch` rather than being
  duplicated per SDK package.

## Generator Ownership Rules

- Treat generated TypeScript SDK outputs as generator-owned artifacts.
- Prefer changing:
  - runtime OpenAPI producers
  - committed OpenAPI artifacts
  - `scripts/release/generate_clients.py`
  - conformance fixtures/tests
  before touching generated SDK output by hand.
- Keep `scripts/release/generate_clients.py --check` as the deterministic gate
  for generated TypeScript SDK artifacts.
- Do not swap or float generator behavior casually; update docs, tests, and
  workflows in the same change if the generation path changes.

## Quality-Gate Matrix

Always-run repo baseline:

- `uv lock --check`
- `uv run ruff check .`
- `uv run ruff check . --select I`
- `uv run ruff format . --check`
- `uv run ty check --force-exclude --error-on-warning packages scripts`
- `uv run mypy`
- `uv run pytest -q`
- `uv run pytest -q packages/nova_file_api/tests/test_generated_client_smoke.py`
- `uv run python scripts/contracts/export_openapi.py --check`
- `uv run python scripts/release/generate_runtime_config_contract.py --check`
- `uv run python scripts/release/generate_clients.py --check`
- `uv run python scripts/release/generate_python_clients.py --check`
- workspace Python build verification for package/app units
- if `packages/nova_runtime_support` changes, build it explicitly

Canonical typing gates:

- `uv run ty check --force-exclude --error-on-warning packages scripts`
- `uv run mypy`

`ty` is the required full-repo type gate. `mypy` remains the required
compatibility backstop until `ty` reaches stable strictness parity for this
monorepo.

Additional required gates when touching OpenAPI, generated TypeScript SDKs, npm
packaging, release automation, or SDK docs/contracts:

- `uv run python scripts/conformance/check_typescript_module_policy.py`
- `npm run -w @nova/sdk-fetch build`
- `npm run -w @nova/sdk-fetch typecheck`
- `npm run -w @nova/sdk-auth typecheck`
- `npm run -w @nova/sdk-file typecheck`
- `npm run -w @nova/contracts-ts-conformance typecheck`
- `npm run -w @nova/contracts-ts-conformance verify`
- `uv run pytest -q scripts/release/tests/test_typescript_sdk_contracts.py`

Additional required gates when touching infra, workflow contracts, or docs
governance:

- `uv run --with cfn-lint==1.46.0 cfn-lint infra/nova/*.yml infra/nova/deploy/*.yml infra/runtime/**/*.yml`
- `uv run --with pytest pytest -q tests/infra/test_absorbed_infra_contracts.py tests/infra/test_workflow_productization_contracts.py tests/infra/test_workflow_contract_docs.py tests/infra/test_docs_authority_contracts.py`

## Documentation Synchronization Rules

- Preserve useful operator instructions unless they are wrong, stale,
  duplicated, broken, or conflicting.
- Keep `AGENTS.md` concise and durable; move deeper explanatory material here or
  into the relevant authority docs.
- Runtime env/override guidance must not fork into handwritten copies; use
  `packages/nova_file_api/src/nova_file_api/config.py` plus
  `scripts/release/runtime_config_contract.py` as authority and keep
  `docs/plan/release/runtime-config-contract.generated.md` fresh.
- If the change affects behavior, contracts, workflows, or durable operator
  routing, update the router docs in the same PR:
  - `AGENTS.md`
  - `README.md`
  - `docs/README.md`
  - `docs/architecture/README.md`
  - `docs/standards/README.md`
  - `docs/runbooks/README.md`
  - `docs/plan/PLAN.md`
- Active docs must link only to truthful, existing active authority paths.
- Historical material belongs under `docs/history/**` or superseded ADR/SPEC
  paths, not in active instructions.

## Pre-commit Policy

- Install hooks with `uv run pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push`.
- If `uv` is not on `PATH`, bootstrap it first, then run
  `scripts/dev/install_hooks.sh`.
- Cheap autofixing and file-hygiene hooks run at `pre-commit`.
- `typing-gates` runs at `pre-push`.
- Manual hooks mirror the AGENTS task router:
  - `typing-gates`
  - `quality-gates`
  - `sdk-conformance`
  - `infra-contracts`
  - `docker-release-images`
- `ty` is enforced in the required local and CI typing gates. It does not need
  a separate branch-protection context because it is part of `quality-gates`.

## Downstream and Retirement Spot Checks

When changing runtime routes or bridge integration, spot check the Dash
downstream consumer:

```bash
export DASH_PCA_REPO=/path/to/dash-pca
rg -n "/v1/transfers|/v1/jobs|nova_dash_bridge|nova_file_api" \
  "${DASH_PCA_REPO:?set DASH_PCA_REPO to your dash-pca checkout}"
```

When touching docs or route authority, ensure retired `container-craft`
references stay archived:

```bash
rg -n "container-craft" README.md docs/architecture docs/plan docs/runbooks \
  | rg -v "docs/history|docs/architecture/adr/superseded|docs/architecture/spec/superseded|historical|archive|retired|ADR-0001|SPEC-0013|SPEC-0014|requirements.md|RELEASE-VERSION-MANIFEST"
```

## Do Not Reintroduce

- stale authority filenames in active docs
- package-root exports or barrels for generated TypeScript SDKs
- runtime validation libraries in generated TypeScript SDK packages
- internal-only operations or models in generated SDK surfaces
- JSON-only shortcuts for operations that declare multiple request media types
- hand-edited generated SDK outputs as the primary fix path
- removal of R scaffolding, TS conformance assets, or runtime support helpers
  because they look unused
