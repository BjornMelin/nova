# Executive Audit

## Mandate

This document is the deeper, independent pass over the first Nova review. I did **not** let the existing repo ADRs, rules, specs, or package topology constrain the conclusions. I used them only as input signals, then re-scored the architecture from a green-field perspective.

## Bottom line

The first-pass conclusions were directionally correct, but they were not aggressive enough in three areas:

1. the public auth contract should be simplified further than "inline auth service" alone
2. the worker should stop calling the API over HTTP to write back results
3. the R SDK strategy should explicitly reject the OpenAPI Generator beta client and move toward a thin `httr2` package

The final target state is materially smaller and cleaner than the current repo:

- one runtime API service instead of file API + auth API
- one auth story for public callers: bearer JWT, scope derived from claims
- one worker result path: direct persistence/service mutation, no self-callback HTTP
- one canonical async Python surface
- one thin TS runtime on `openapi-fetch`
- one thin Python generation layer on top of `openapi-python-client`
- one thin R package built around `httr2`
- one AWS platform topology centered on ECS/Fargate

## What I validated from the first pass

The following first-pass recommendations survived the deeper audit and remain final:

- Delete the dedicated auth service and inline JWT verification into the file API.
- Use native async JWT verification and framework-level dependency integration rather than threadpool-offloaded sync verification.
- Replace per-service HTTP middleware duplication with one shared pure-ASGI middleware layer.
- Make the runtime public surface async-first instead of sync-over-async.
- Rebase the TypeScript SDK onto `openapi-typescript` + `openapi-fetch` and delete the custom TS fetch runtime.
- Keep `openapi-python-client`, but slash the post-processing surface by moving customization into config/templates.
- Keep ECS/Fargate behind ALB as the target compute/front-door combination for the steady API + worker shape.

## What changed after the deeper pass

The independent pass elevated these new or sharpened decisions into the final plan:

- Hard-cut the public auth contract to bearer JWT only. Remove `session_id`, `X-Session-Id`, and `X-Scope-Id` semantics from the public API.
- Delete the worker's internal HTTP callback path and worker token; update job results directly through shared runtime services/repositories.
- Treat the remaining OpenAPI mutation layer as a code smell to aggressively eliminate via native FastAPI route declarations, security dependencies, `responses=`, and a small `generate_unique_id_function` only if needed.
- Explicitly reject OpenAPI Generator's R client for Nova. Its R generator is beta and lacks important auth/schema support, so the right answer is a thin `httr2` package.
- Rebaseline the entire repo after the architecture cuts. Deleting systems without deleting their release logic, docs, tests, and workflows would leave the repo looking half-refactored.

## Current-state findings from the codebase

### 1) Split-brain authentication

Nova currently duplicates auth behavior across:

- `packages/nova_file_api/src/nova_file_api/auth.py`
- `packages/nova_auth_api/src/nova_auth_api/service.py`
- `packages/nova_sdk_auth/`
- `packages/nova_sdk_py_auth/`
- `packages/nova_sdk_r_auth/`

The file API still supports multiple auth modes, including remote verification over HTTP. The auth API separately verifies JWTs with a sync verifier. This is duplicated code, duplicated release surface, duplicated CI surface, and duplicated operational surface.

### 2) Public session scope is not domain data

Public request bodies in `packages/nova_file_api/src/nova_file_api/models.py` carry `session_id`, and routes pass it into auth resolution. But transfer orchestration is keyed off the authenticated principal's scope, not off `session_id` as independent domain data. That makes `session_id` public-contract entropy rather than a real business requirement.

### 3) Worker self-calls the API

`packages/nova_file_api/src/nova_file_api/worker.py` posts result updates to `/v1/internal/jobs/{job_id}/result` using `httpx`. The API route then immediately calls the job service. That is an internal network hop whose only job is to bridge code that already lives in the same package.

### 4) OpenAPI emission is over-customized

`packages/nova_file_api/src/nova_file_api/openapi.py`, `packages/nova_auth_api/src/nova_auth_api/openapi.py`, and `packages/nova_runtime_support/src/nova_runtime_support/openapi.py` perform a large amount of contract mutation after FastAPI builds the schema. That is mostly compensating for design choices that should be expressed in the route layer.

### 5) The public Python surface is inverted

`nova_dash_bridge` wraps an async core in a sync façade and then calls that sync façade from async FastAPI routes via a threadpool. That is the wrong polarity for a FastAPI-centric runtime.

### 6) SDK generation is oversized

The largest non-test scripts in the repo are:

| Script | Nonblank LOC | Current role |
| --- | --- | --- |
| `scripts/release/generate_python_clients.py` | 2,487 | Python SDK generation + output patching |
| `scripts/release/generate_clients.py` | 1,864 | TypeScript + R SDK generation + runtime synthesis |

The codebase is spending a lot of engineering effort compensating for generator/runtime design choices that modern dependencies already solve more directly.

## Repo-size baseline

| Area | Files | Nonblank LOC |
| --- | --- | --- |
| packages/ | 291 | 34780 |
| docs/ | 147 | 13664 |
| scripts/ | 45 | 12096 |
| infra/ | 23 | 5218 |
| tests/ | 9 | 2541 |

Largest package clusters:

| Package | Files | Nonblank LOC |
| --- | --- | --- |
| nova_file_api | 58 | 12911 |
| nova_sdk_py_file | 77 | 5058 |
| contracts | 39 | 4854 |
| nova_dash_bridge | 19 | 3136 |
| nova_sdk_file | 8 | 2467 |
| nova_auth_api | 23 | 1587 |
| nova_sdk_py_auth | 26 | 1557 |
| nova_sdk_auth | 8 | 795 |
| nova_sdk_r_file | 9 | 785 |
| nova_runtime_support | 9 | 697 |
| nova_sdk_r_auth | 9 | 557 |
| nova_sdk_fetch | 6 | 376 |

Guaranteed deletions from the final plan:

| Cluster | Files removed | Nonblank LOC removed |
| --- | --- | --- |
| Standalone auth service + auth SDKs | 67 | 4,535 |
| `@nova/sdk-fetch` | 6 | 376 |
| Guaranteed minimum total | 73 | 4,911 |

## Final decisions

| Decision | Final score /10 |
| --- | --- |
| Inline async JWT verification into nova_file_api and delete the dedicated auth service plus auth SDKs. | 9.68 |
| Remove public `session_id`, `X-Session-Id`, and `X-Scope-Id` semantics; derive caller scope exclusively from authenticated JWT claims. | 9.44 |
| Remove the worker's internal HTTP callback and have the worker update jobs, activity, and metrics directly via shared services/repositories. | 9.53 |
| Replace bespoke OpenAPI mutation and operation-id scaffolding with native FastAPI features: `responses`, security dependencies, router metadata, and a custom `generate_unique_id_function` only where required. | 9.31 |
| Move request context propagation and common error-envelope handling into a single shared pure ASGI layer and shared exception-registration primitives. | 9.14 |
| Make `nova_file_api.public` async-first, call it directly from FastAPI integrations, and keep truly necessary sync adapters only for Dash/Flask consumers. | 9.41 |
| Replace the custom `@nova/sdk-fetch` runtime and bulky TS generation logic with `openapi-typescript` plus `openapi-fetch` and thin Nova-specific auth/base-url assembly. | 9.47 |
| Keep `openapi-python-client`, but move Nova-specific customizations into generator config and a very small custom-template layer, deleting most post-generation patching logic. | 9.24 |
| Do not adopt OpenAPI Generator's beta R client. Build/retain a thin httr2-based Nova R package with minimal generated operation metadata and idiomatic auth/request helpers. | 9.13 |
| Finalize the target platform as CloudFront (+WAF) → ALB → ECS/Fargate, with one public API service and one worker service, plus S3, SQS, DynamoDB, Secrets Manager/SSM, and ADOT-based observability. | 9.22 |
| After the architectural cuts land, rebaseline the repo: workspace members, dependency floors, CI matrix, release flow, docs, manifests, and verification commands around the smaller system. | 9.17 |

## Final conclusion

The best final Nova is **not** an optimized version of the current two-service runtime. It is a **single-service API + worker platform** with a much thinner SDK and contract toolchain.

The current repo has good foundations — FastAPI, aioboto3, Pydantic, uv, and typed clients — but it is paying an unnecessary tax in duplicated auth, contract mutation, adapter layering, and custom SDK runtime code. The implementation program in this pack is designed to delete those taxes decisively.
