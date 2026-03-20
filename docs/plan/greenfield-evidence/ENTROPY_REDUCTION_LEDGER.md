# Entropy Reduction Ledger

## Why this matters

The Nova refactor program is not only about correctness; it is about reducing the long-term maintenance surface:

- fewer deployable units
- fewer packages
- fewer generated artifacts
- fewer custom transport layers
- fewer duplicate code paths
- fewer docs/workflows/manifests to keep synchronized

## Baseline size

| Area | Files | Nonblank LOC |
| --- | --- | --- |
| packages/ | 291 | 34780 |
| docs/ | 147 | 13664 |
| scripts/ | 45 | 12096 |
| infra/ | 23 | 5218 |
| tests/ | 9 | 2541 |

## Largest current maintenance hotspots

| Hotspot | Files | Nonblank LOC | Why it is expensive |
| --- | --- | --- | --- |
| `packages/nova_file_api` | 58 | 12911 | largest runtime package; currently also carries auth, OpenAPI customizations, worker HTTP callback, and public surface glue |
| `packages/nova_sdk_py_file` | 77 | 5058 | large generated Python client plus generator coupling |
| `packages/contracts` | 39 | 4854 | contract artifacts + fixtures that must match runtime reality |
| `packages/nova_dash_bridge` | 19 | 3136 | adapter complexity from sync/async inversion |
| `scripts/release/generate_python_clients.py` | 1 | 2,487 | large bespoke patch script |
| `scripts/release/generate_clients.py` | 1 | 1,864 | large TS/R generator/runtime synthesis script |

## Guaranteed deletions

These are concrete deletions that the program intentionally makes rather than merely refactors.

| Cluster | Files removed | Nonblank LOC removed |
| --- | --- | --- |
| Standalone auth service + auth SDKs + auth app image | 67 | 4535 |
| `@nova/sdk-fetch` package | 6 | 376 |
| Guaranteed minimum total | 73 | 4911 |

## Branch-by-branch reduction estimates

| Branch | Guaranteed files removed | Guaranteed LOC removed | Likely total LOC reduction range | Notes |
| --- | --- | --- | --- | --- |
| 01 feat/api-inline-async-jwt-auth | 67 | 4535 | 4835–5435 | Deletes standalone auth service, auth SDK packages, auth app image, and related manifests/workflow references. |
| 02 feat/api-strip-session-scope-from-public-contract | 0 | 0 | 250–800 | Removes `session_id` fields and same-origin auth plumbing from models, routes, tests, docs, and SDKs. |
| 03 refactor/worker-direct-job-result-updates | 0 | 0 | 200–500 | Deletes internal result-update route and worker callback config/HTTP logic. |
| 04 refactor/api-native-fastapi-openapi | 0 | 0 | 350–900 | Collapses large `openapi.py` mutation logic and most operation-id registry scaffolding. |
| 05 refactor/runtime-pure-asgi-middleware-errors | 0 | 0 | 120–300 | Moves duplicated middleware/error glue into one shared pure-ASGI implementation. |
| 06 refactor/public-async-first-surface | 0 | 0 | 300–900 | Deletes sync-over-async event-loop helpers and threadpool bridge indirection. |
| 07 refactor/sdk-typescript-openapi-fetch | 6 | 376 | 1276–2576 | Deletes `@nova/sdk-fetch` and materially shrinks TypeScript generator/output complexity. |
| 08 refactor/sdk-python-template-thin | 0 | 0 | 1200–1800 | Shrinks `generate_python_clients.py` and associated output patching substantially. |
| 09 refactor/sdk-r-httr2-thin-client | 0 | 0 | 250–700 | Replaces bespoke R runtime layers with thin httr2-oriented code. |
| 10 infra/greenfield-ecs-platform | 0 | 0 | 200–800 | Deletes auth-service infra and simplifies deployment topology and runbooks. |
| 11 chore/repo-rebaseline-ci-release | 0 | 0 | 300–900 | Prunes stale workflows, docs, manifests, and release scripts after earlier cuts. |

## Program-level reduction target

- **Guaranteed minimum**: 73 files / 4911 nonblank LOC deleted
- **Likely total reduction**: 9281–15611 nonblank LOC
- **Likely package-count reduction**: from 12 package clusters under `packages/` to 7 actively maintained clusters
- **Likely deployable-service reduction**: from 2 public services to 1 public service + 1 worker service

## Where the biggest cognitive-load reduction happens

The raw LOC deletion matters, but the bigger win is deleting **coordination burden**:

1. one auth model instead of multiple auth modes and services
2. one OpenAPI source of truth instead of route code plus mutation code plus operation-id registries
3. one worker result path instead of direct work plus an internal HTTP callback
4. one TS transport runtime instead of a private fetch package
5. one thin Python generator strategy instead of thousands of lines of repair logic
6. one thin R package strategy instead of a second custom runtime

## Interpretation

A 500-line deletion that removes an entire category of maintenance work is better than a 2,000-line local code cleanup that leaves the architecture unchanged.

This ledger therefore values:

- whole-system deletions
- package deletions
- release-unit deletions
- workflow/manifests/docs synchronization reductions

at least as much as raw code deletion.
