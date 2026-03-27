# Green-field simplification program

Status: Active program index
Last updated: 2026-03-24

Canonical authority for **decisions** lives in
[ADR-0033](../architecture/adr/ADR-0033-single-runtime-auth-authority.md)
through
[ADR-0041](../architecture/adr/ADR-0041-shared-pure-asgi-middleware-and-errors.md)
and
[SPEC-0027](../architecture/spec/SPEC-0027-public-http-contract-revision-and-bearer-auth.md)
through
[SPEC-0030](../architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md).
This document is the **execution router**: branch order, merge policy, and
definition of done.

ID mapping from the original Codex pack:
[greenfield-authority-map.md](./greenfield-authority-map.md).

Implementation prompts remain under
[`.agents/nova_greenfield_codex_pack/prompts/`](../../.agents/nova_greenfield_codex_pack/prompts/)
as non-authoritative playbooks.

## Program philosophy

- Break cleanly; delete aggressively; do not preserve obsolete compatibility
  layers.
- Prefer dependency-native capabilities over repo-private wrappers when the
  dependency already solves the problem.
- Keep every branch mergeable, verified, and easy to review.

## Branch dependency graph

```text
1 inline async jwt auth + delete auth service
  -> 2 remove public session/same-origin contract
    -> 3 remove worker HTTP result callback
      -> 4 native FastAPI contract / OpenAPI
        -> 5 shared pure-ASGI middleware + errors
          -> 6 async-first public surface
            -> 7 TS SDK on Hey API
              -> 8 Python SDK thin templates
                -> 9 R SDK thin httr2 client
                  -> 10 infra simplification onto final platform
                    -> 11 repo/CI/release/doc rebaseline
```

## Machine-readable run order (from pack manifest)

| Order | Branch | Semver | Depends on | Decision (summary) |
| --- | --- | --- | --- | --- |
| 1 | `feat/api-inline-async-jwt-auth` | MAJOR | latest main | Inline async JWT in `nova_file_api`; delete dedicated auth service and auth SDKs. |
| 2 | `feat/api-strip-session-scope-from-public-contract` | MAJOR | branch 1 merged | Remove public `session_id`, `X-Session-Id`, `X-Scope-Id`; scope from JWT claims only. |
| 3 | `refactor/worker-direct-job-result-updates` | MAJOR | branch 2 merged | Worker updates jobs/activity/metrics via shared services; no internal HTTP callback. |
| 4 | `refactor/api-native-fastapi-openapi` | MAJOR | branch 3 merged | Native FastAPI OpenAPI expression with explicit route `operation_id`s, route-declared `responses=`, and no file-API post-processor. |
| 5 | `refactor/runtime-pure-asgi-middleware-errors` | MAJOR | branch 4 merged | Shared pure ASGI request-context middleware, shared FastAPI exception registration, and canonical request-id/error-envelope parity. |
| 6 | `refactor/public-async-first-surface` | MAJOR | branch 5 merged | `nova_file_api.public` async-first; thin sync adapters only at true sync edges. |
| 7 | `refactor/sdk-typescript-hey-api` | MAJOR | branch 6 merged | `@hey-api/openapi-ts`; remove custom TS fetch runtime package and unify on `@nova/sdk`. |
| 8 | `refactor/sdk-python-template-thin` | MAJOR | branch 7 merged | `openapi-python-client` with config + minimal templates; slash patch scripts. |
| 9 | `refactor/sdk-r-httr2-thin-client` | MAJOR | branch 8 merged | Thin `httr2` R package; reject OpenAPI Generator R beta as primary path. |
| 10 | `infra/greenfield-ecs-platform` | MAJOR | branch 9 merged | Finalize CloudFront + WAF public edge, internal ALB origin, ECS/Fargate API + worker, and managed data-plane IaC/documentation truth. |
| 11 | `chore/repo-rebaseline-ci-release` | MAJOR | branch 10 merged | Rebaseline workspace, locks, CI, release, and docs for the smaller system. |

## Why this order

1. **Auth topology first** — drives contract shape, OpenAPI security, SDKs,
   infra, and release artifacts.
2. **Public contract before SDK regeneration** — stabilize HTTP/auth before
   client rebuilds.
3. **Worker callback early** — removes a high-entropy boundary before OpenAPI
   and middleware refactors.
4. **Branches 4–6 before 7–9** — contract and public surface stable before
   per-language SDK work.
5. **Infra after runtime shape** — templates describe the final topology.
6. **Rebaseline last** — one coherent pass so the repo does not read
   half-migrated.

## Merge policy

For each branch:

1. Create from latest `main`.
2. Run the corresponding prompt under `.agents/nova_greenfield_codex_pack/prompts/`.
3. Open a PR to `main`.
4. Do not start the next branch until the PR is merged and `main` is green.
5. If facts change, update ADRs, SPECs, this file, and downstream prompts in the
   same change set where practical ([SPEC-0020](../architecture/spec/SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)).

## Mandatory reviewer questions

- Did this branch delete obsolete code completely?
- Did it replace custom behavior with a dependency-native feature where possible?
- Did it reduce long-term synchronization burden?
- Are docs, OpenAPI, SDK outputs, and release scripts aligned with the new truth?
- Are verification commands passing?
- Is the architecture cleaner for Python, TypeScript, and R consumers?

## Global verification baseline

Commands must remain runnable or be updated deliberately when artifact flow
changes:

```bash
uv sync --locked --all-packages --all-extras --dev
uv lock --check
uv run ruff check .
uv run ruff check . --select I
uv run ruff format . --check
uv run ty check --force-exclude --error-on-warning packages scripts
uv run mypy
uv run pytest -q
uv run python scripts/contracts/export_openapi.py --check
uv run python scripts/release/generate_runtime_config_contract.py --check
uv run python scripts/release/generate_clients.py --check
uv run python scripts/release/generate_python_clients.py --check
for p in packages/nova_file_api packages/nova_dash_bridge packages/nova_runtime_support; do uv build "$p"; done
npm run -w @nova/sdk build
npm run -w @nova/sdk typecheck
bash scripts/checks/verify_r_cmd_check.sh packages/nova_sdk_r
```

## Program-level definition of done

The program is complete only when all of the following are true:

- The standalone auth service and auth-only SDK packages are removed.
- Public `session_id` / header scope surrogates for auth are removed.
- Worker HTTP result callback to the API is removed.
- The custom TypeScript fetch runtime package is removed (replaced by
  ecosystem-native Hey API generation per ADR-0037 / SPEC-0030).
- Remaining OpenAPI customization is small and justified (ADR-0036).
- The canonical public Python surface is async-first (ADR-0037).
- Generated clients for Python, TypeScript, and R target the final public
  contract cleanly.
- Infra, docs, CI, and release flow match the smaller system, with Python 3.11
  as the supported workspace floor, Python 3.13 as the primary tooling
  baseline, and Python 3.11 plus 3.12 kept as verified runtime compatibility
  coverage for surviving packages.
- A new maintainer can understand the repo without a stack of exception docs.

## If a branch uncovers a better option

Breaking changes are allowed; discipline still matters:

1. Score against the same framework as the relevant ADR.
2. Switch only if the new option scores **≥ 9.0** and clearly beats the planned
   winner.
3. Record what changed, why, new score, and affected prompts/docs.

## What not to do

- Do not keep dead packages “temporarily”.
- Do not add compatibility shims for deleted auth/session contracts.
- Do not replace one custom runtime with another custom runtime.
- Do not keep release units for deleted packages.
- Do not leave superseded topology docs on the main authority path ([IR-0014](../architecture/requirements.md#ir-0014-superseded-architecture-archive-boundary)).

## Changelog

- 2026-03-24: Refreshed the global verification baseline after branch 11
  rebaseline completion.
- 2026-03-19: Canonicalized from `.agents/nova_greenfield_codex_pack` with Nova
  ADR/SPEC cross-links.
