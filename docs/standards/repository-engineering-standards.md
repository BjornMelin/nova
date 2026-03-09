# Repository Engineering Standards

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-09

## Purpose

Capture durable repo engineering/operator rules that are too detailed for
`AGENTS.md` but should still guide fresh-context sessions.

## Reading order for fresh sessions

1. `AGENTS.md`
2. `README.md`
3. `docs/overview/NOVA-REPO-OVERVIEW.md`
4. the relevant authority docs:
   - runtime API: `SPEC-0000`, `SPEC-0015`, `SPEC-0016`
   - public SDK governance: `ADR-0013`, `SPEC-0011`, `SPEC-0012`
   - deploy-validation/control-plane: `SPEC-0017` through `SPEC-0023`
5. `docs/runbooks/README.md` when the task affects release or operations

## Public TypeScript SDK rules

- Public TypeScript packages are `@nova/sdk-auth`, `@nova/sdk-file`, and the
  shared runtime/helper package `@nova/sdk-fetch`.
- Public imports are subpath-only. Do not add package-root `"."` exports.
- Do not create `index.ts` files or re-export barrels.
- Public `types` surfaces stay curated; do not expose raw whole-spec aliases or
  internal-only worker models.
- Internal/admin operations marked with `x-nova-sdk-visibility: internal` stay
  excluded from public SDK generation.
- Public TypeScript SDKs are validation-free. Do not add `zod`, validator
  packages, validator subpaths, or runtime request/response validation helpers.
- OpenAPI remains the only schema authority for SDK generation.
- Multi-media request bodies must preserve explicit generated `contentType`
  selection instead of collapsing to JSON-only behavior.
- Shared transport/runtime logic belongs in `@nova/sdk-fetch` rather than being
  duplicated per SDK package.

## Generator ownership rules

- Treat generated TypeScript SDK outputs as generator-owned artifacts.
- Prefer changing:
  - runtime OpenAPI producers
  - committed OpenAPI artifacts
  - `scripts/release/generate_clients.py`
  - conformance fixtures/tests
  before touching generated SDK output by hand.
- Keep `scripts/release/generate_clients.py --check` as the deterministic gate
  for public TypeScript SDK artifacts.
- Do not swap or float generator behavior casually; update docs, tests, and
  workflows in the same change if the generation path changes.

## Quality-gate matrix

Always-run repo baseline:

- `uv lock --check`
- `uv run ruff check .`
- `uv run ruff check . --select I`
- `uv run ruff format . --check`
- `uv run mypy`
- `uv run pytest -q`
- generated client smoke pytest
- `uv run python scripts/contracts/export_openapi.py --check`
- `uv run python scripts/release/generate_clients.py --check`
- `uv run python scripts/release/generate_python_clients.py --check`
- workspace Python build verification

Additional required gates when touching OpenAPI, public TypeScript SDKs, npm
packaging, release automation, or SDK docs/contracts:

- `uv run python scripts/conformance/check_typescript_module_policy.py`
- `npm run -w @nova/sdk-fetch build`
- `npm run -w @nova/sdk-fetch typecheck`
- `npm run -w @nova/sdk-auth typecheck`
- `npm run -w @nova/sdk-file typecheck`
- `npm run -w @nova/contracts-ts-conformance typecheck`
- `npm run -w @nova/contracts-ts-conformance verify`
- `uv run pytest -q scripts/release/tests/test_typescript_sdk_contracts.py`

## Documentation synchronization rules

- Preserve existing operator instructions unless they are wrong, stale,
  duplicated, broken, or in conflict.
- Keep `AGENTS.md` concise and durable; move longer explanatory material here or
  into the relevant authority docs.
- Any change to public SDK topology, generation behavior, release validation, or
  conformance rules must update `AGENTS.md`, relevant README/overview docs, and
  the relevant ADR/SPEC/runbook docs in the same PR.
- Active docs must link only to truthful, existing active authority paths.
- Historical material belongs under `docs/history/**` or superseded ADR/SPEC
  paths, not in active instructions.

## Do not reintroduce

- stale authority filenames in active docs
- package-root exports or barrels for public TypeScript SDKs
- runtime validation libraries in public TypeScript SDK packages
- internal-only operations or models in public SDK surfaces
- JSON-only shortcuts for operations that declare multiple request media types
- hand-edited generated SDK outputs as the primary fix path
- removal of R scaffolding, TS conformance assets, or generator/runtime support
  because they look unused
