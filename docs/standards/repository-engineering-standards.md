# Repository Engineering Standards

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-25

## Purpose

Capture durable repo engineering and operator rules that are too detailed for
`AGENTS.md` but should still guide fresh-context sessions.

## Reading Order for Fresh Sessions

1. `AGENTS.md`
2. `docs/README.md`
3. `docs/architecture/README.md`
4. `README.md`
5. `docs/runbooks/README.md` when the task affects release or operations

## Authority Classification

`docs/architecture/README.md` is the sole narrative authority map for active
architecture packs, the canonical route chain, and deploy-governance pack
membership. Do not recreate competing pack summaries in other top-level router
docs.

## Workflow Mapping

Use the repo workflows as the enforcement map:

- `.github/workflows/ci.yml`
  - Python 3.13 primary quality/generation lane, Python 3.11 and 3.12 runtime
    compatibility coverage, generated-client checks, TS/R conformance,
    required `ty` plus `mypy` compatibility backstop, canonical-route guard
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

## Release operator docs profile (`docs/runbooks/**`)

Rules for narrative provisioning, release, and validation markdown under
`docs/runbooks/release/**` and `docs/runbooks/provisioning/**` (indexes:
`docs/runbooks/README.md`, `docs/runbooks/release/README.md`,
`docs/runbooks/provisioning/README.md`):

1. **Naming:** New files use kebab-case. Exceptions: `README.md`, and
   machine-stable uppercase artifacts under `docs/release/` that automation
   consumes (for example `RELEASE-VERSION-MANIFEST.md`).
2. **Operator guide sections:** Each guide should include `Purpose`,
   `Prerequisites`, `Inputs`, `Step-by-step commands`, `Acceptance checks`, and
   `References` where applicable.
3. **Placeholders:** Use `${AWS_ACCOUNT_ID}`, `${AWS_REGION}`, `${PROJECT}`,
   etc.; never commit live secrets.
4. **Review cadence:** Keep `Last reviewed` / `Last updated` current; re-read
   after CI/CD or infra contract changes (at least every 90 days for high-churn
   guides).
5. **Final-state clarity:** Active release docs describe implemented, executable
   behavior only. Superseded or exploratory plans belong under
   `docs/history/**`.
6. **Authority:** Do not duplicate ADR/SPEC contracts; link the
   [canonical documentation authority chain](../runbooks/release/README.md#canonical-documentation-authority-chain)
   or architecture indexes instead.
7. **Nova-path guardrail:** Active operator paths stay under `docs/**`; do not
   cite retired external Nova doc trees as current guidance. Infra contract
   tests enforce active-path rules.

## Generated TypeScript SDK Rules

- Generated TypeScript package is `@nova/sdk`.
- Release-grade packaging for the TypeScript SDK stays within Nova's existing
  CodeArtifact staged/prod system, while artifacts remain generator-owned and
  subpath-only.
- Publicly supported imports remain subpath-only. Do not add package-root `"."`
  exports.
- Do not create `index.ts` files or re-export barrels.
- `types` surfaces stay curated; do not expose raw whole-spec aliases or
  internal-only worker models.
- Internal/admin operations marked with `x-nova-sdk-visibility: internal` stay
  excluded from generated SDK output.
- Generated TypeScript SDKs are intentionally free of bundled validation
  libraries. Do not add `zod`, validator packages, validator subpaths, or
  runtime request/response validation helpers.
- OpenAPI remains the only schema authority for SDK generation.
- Multi-media request bodies must preserve explicit generated `contentType`
  selection instead of collapsing to JSON-only behavior.
- The checked-in `@nova/sdk/client` module is the generator-owned Hey API fetch
  client instance; do not reintroduce a repo-private transport/runtime package.
- Configure auth/header customization through `client.setConfig()` and request
  interceptors on `@nova/sdk/client`, and call generated operations from
  `@nova/sdk/sdk`.

## R Package Rules

- R SDK packages are first-class internal release artifacts, not deferred
  generated catalogs.
- The package line is `nova`, with repository path under
  `packages/nova_sdk_r/`.
- R packages use real package scaffolds, `logical format r`, generator-owned
  output from `scripts/release/generate_clients.py`, testthat coverage, and
  verification through the shared `scripts/checks/verify_r_cmd_check.sh`
  helper. The helper runs `R CMD build` and `R CMD check --no-manual`,
  parses `00check.log`, and fails the lane if `R CMD check` reports warnings
  without requiring `pdflatex` on CI or release runners. When regenerating,
  the generator preserves an existing `DESCRIPTION` version instead of
  resetting it.
- Keep generator-owned R metadata current with the validated CRAN toolchain,
  but pin dependency floors to the smallest locally verified passing versions
  instead of assuming the newest CRAN release is already present on release
  runners.
- Public R wrappers must expose concrete OpenAPI path/query parameters instead
  of generic `path_params` / `query` bags. Keep generic escape hatches limited
  to headers and constructor-level defaults.
- For the current public file API contract, the generated R runtime stays
  JSON-only. Do not preserve dead form or multi-media request handling in the R
  client unless the committed OpenAPI contract actually requires it.
- R release artifacts are transported through CodeArtifact generic packages and
  must retain signed tarball and detached `.sig` evidence in the release
  workflow.
- Keep the release evidence and package metadata deterministic; do not invent
  a separate internal registry or CRAN-style public publishing path.

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
- Run `npm ci` before `scripts/release/generate_clients.py --check` so the
  repo-installed `@hey-api/openapi-ts` CLI is available without ad hoc fetches.
- Do not swap or float generator behavior casually; update docs, tests, and
  workflows in the same change if the generation path changes.

## Quality-Gate Matrix

Always-run repo baseline:

- `uv sync --locked --all-packages --all-extras --dev`
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
- `packages/nova_file_api`, `packages/nova_dash_bridge`, and
  `packages/nova_runtime_support` build verification

Canonical typing gates:

- `uv run ty check --force-exclude --error-on-warning packages scripts`
- `uv run mypy`

`ty` is the required full-repo type gate. `mypy` remains the required
compatibility backstop until `ty` reaches stable strictness parity for this
monorepo.

Toolchain baseline notes:

- Workspace packages support Python 3.11+.
- Python 3.13 is the primary CI/tooling baseline. Keep Python 3.11 and 3.12
  compatibility for the surviving runtime packages through the dedicated
  pytest/build lane unless a deliberate repo-wide support-floor decision
  removes either lane.
- `pyproject.toml` pins the supported `uv` CLI via
  `[tool.uv].required-version` (currently `0.11.1`); keep CI and local
  bootstrap flows on that version unless a repo-wide verification run
  intentionally bumps it.
- Node 24 LTS is the primary npm/TypeScript SDK tooling baseline for local
  `npm ci`, the TypeScript conformance/package lanes in `Nova CI`, and the
  npm packaging steps in `Publish Packages`.
- The current npm workspace, generated SDKs, and conformance fixtures stay on
  the verified TypeScript 5.x line. TypeScript 6 remains deferred until a
  repo-wide migration updates `package-lock.json`, generated SDK outputs,
  conformance fixtures, and release/workflow docs in one verified change set.
- The root dev dependency group pins `openapi-python-client==0.28.3` for the
  committed Python SDK generation path. Keep that exact pin, the lockfile,
  `scripts/release/openapi_python_client/`, and the committed
  `packages/nova_sdk_py` tree aligned in the same change.
- Current runtime dependency floors are manifest-owned authority:
  `pydantic-settings>=2.13.1` in `nova-file-api` and `nova-dash-bridge`, plus
  `uvicorn[standard]>=0.42.0` in `nova-file-api`. If those
  floors move, update docs, lockfiles, and verification guidance together.
- Pytest defaults to `--import-mode=importlib` and relies on editable workspace
  installs instead of repo-level `pythonpath` injection. Treat any return to a
  global `pythonpath` shim as a regression unless it is backed by a newly
  reproduced import failure.

Additional required gates when touching OpenAPI, generated TypeScript SDKs, npm
packaging, release automation, or SDK docs/contracts:

- `uv run python scripts/conformance/check_typescript_module_policy.py`
- `npm run -w @nova/sdk typecheck`
- `npm run -w @nova/sdk build`
- `npm run -w @nova/contracts-ts-conformance typecheck`
- `npm run -w @nova/contracts-ts-conformance verify`
- `uv run pytest -q scripts/release/tests/test_typescript_sdk_contracts.py`

Additional required gates when touching R package artifacts, release packaging,
or R SDK docs/contracts:

- `bash scripts/checks/verify_r_cmd_check.sh <package-dir>` (or the repo-local
  conformance entrypoint that invokes it); the helper runs `R CMD build` and
  `R CMD check --no-manual`, parses `00check.log`, and fails on warnings
- any R package unit tests or documentation generation checks introduced by the
  change

Additional required gates when touching infra, workflow contracts, or docs
governance:

- `bash scripts/checks/run_infra_contracts.sh`
- `uv run --with pytest pytest -q tests/infra/test_ci_scope_detector.py tests/infra/test_release_workflow_contracts.py tests/infra/test_serverless_stack_contracts.py tests/infra/test_workflow_contract_docs.py tests/infra/test_docs_authority_contracts.py`

## Documentation Synchronization Rules

- Preserve useful operator instructions unless they are wrong, stale,
  duplicated, broken, or conflicting.
- Keep `AGENTS.md` concise and durable; move deeper explanatory material here or
  into the relevant authority docs.
- Runtime env/override guidance must not fork into handwritten copies; use
  `packages/nova_file_api/src/nova_file_api/config.py` plus
  `scripts/release/runtime_config_contract.py` as authority and keep
  `docs/release/runtime-config-contract.generated.md` fresh.
- Runtime settings must declare explicit string `Field(validation_alias=…)`
  env mappings. Contract tooling reads `field.validation_alias` only; do not
  rely on `alias=` or implicit uppercase fallback.
- `docs/clients/README.md` is downstream integration guidance only. It must
  remain subordinate to the active authority docs and not become the primary
  SDK release authority.
- If the change affects behavior, contracts, workflows, or durable operator
  routing, update the router docs in the same PR:
  - `AGENTS.md`
  - `README.md`
  - `docs/README.md`
  - `docs/architecture/README.md`
  - `docs/standards/README.md`
  - `docs/runbooks/README.md`
  - `docs/plan/PLAN.md`
- If the change affects workflow, validation, or release schema contracts,
  update `docs/contracts/README.md` in the same PR.
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
