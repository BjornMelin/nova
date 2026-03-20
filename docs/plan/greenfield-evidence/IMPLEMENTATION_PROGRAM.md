# Implementation Program

## Program philosophy

- break cleanly
- delete aggressively
- do not preserve obsolete compatibility layers
- use dependency-native capabilities instead of repo-private wrappers where the dependency already solves the problem
- keep every branch mergeable, verified, and easy to review

## Branch dependency graph

```text
1 inline async jwt auth + delete auth service
  -> 2 remove public session/same-origin contract
    -> 3 remove worker HTTP result callback
      -> 4 native FastAPI contract / OpenAPI
        -> 5 shared pure-ASGI middleware + errors
          -> 6 async-first public surface
            -> 7 TS SDK on openapi-fetch
              -> 8 Python SDK thin templates
                -> 9 R SDK thin httr2 client
                  -> 10 infra simplification onto final platform
                    -> 11 repo/CI/release/doc rebaseline
```

## Why this order

### Branch 1 first

Authentication topology drives almost everything else:

- public contract shape
- OpenAPI security
- SDK auth models
- infra topology
- deploy artifacts

### Branch 2 before SDK work

The public request/response/auth contract should settle before reworking generated clients.

### Branch 3 before major cleanup

The worker callback is a high-value deletion that simplifies runtime boundaries before OpenAPI and middleware cleanup.

### Branches 4–6 before SDK regeneration

The contract source of truth and public surface should be stable before the SDKs are rebuilt around them.

### Branches 7–9 after contract stabilization

SDK branches then become cleaner and more deterministic.

### Branch 10 after runtime shape is stable

Infra should describe the final runtime topology, not a halfway state.

### Branch 11 last

This is the polish pass that removes the last stale references and rebaselines the repo.

## Merge policy

For each branch:

1. create from latest `main`
2. run the full prompt
3. open a PR to `main`
4. do not start the next branch until the PR is merged and `main` is green
5. if a branch reveals new architecture facts, update:
   - ADRs
   - specs
   - `README_RUN_ORDER.md`
   - the next prompt files if required

## Mandatory reviewer questions for every PR

- Did this branch delete the obsolete code completely?
- Did it replace custom behavior with a dependency-native feature where possible?
- Did it reduce or increase long-term synchronization burden?
- Are docs / OpenAPI / SDK outputs / release scripts aligned with the new truth?
- Are all verification commands passing?
- Is the resulting architecture cleaner for Python, TS, and R consumers?

## Global verification baseline

These commands should remain runnable or be updated deliberately if a branch changes artifact flow:

```bash
uv sync --locked --all-extras --dev
uv run ruff check .
uv run ruff format . --check
uv run mypy .
uv run pytest -q
uv run python scripts/contracts/export_openapi.py --check
uv run python scripts/release/generate_clients.py --check
uv run python scripts/release/generate_python_clients.py --check
npm run -w @nova/sdk-file build
npm run -w @nova/sdk-file typecheck
bash scripts/checks/verify_r_cmd_check.sh packages/nova_sdk_r_file
```

## Program-level definition of done

The program is complete only when all of the following are true:

- the standalone auth service is gone
- auth SDK packages are gone
- public `session_id` auth semantics are gone
- worker HTTP result callback is gone
- the TS fetch runtime package is gone
- the remaining OpenAPI customization layer is small and justified
- the canonical public Python surface is async-first
- generated clients for Python, TS, and R all target the final public contract cleanly
- infra, docs, CI, and release flow match the smaller system
- a new maintainer can understand the repo quickly without reading a stack of exception docs

## What to do if a branch uncovers a better option

Breaking changes are explicitly allowed, but discipline still matters.

If Codex discovers a materially better option mid-branch:

1. score it against the same framework
2. only switch if it scores **>= 9.0** and clearly beats the current planned winner
3. update the branch prompt tracking doc with:
   - what changed
   - why
   - new score
   - affected later prompts/docs

## What not to do

- do not keep dead packages around "temporarily"
- do not add compatibility shims for deleted auth/session contracts
- do not replace one custom runtime with another custom runtime
- do not preserve release units for deleted packages
- do not keep docs for superseded topologies "for reference" inside the main path
- do not shrink text by deferring decisions; decide and cut
