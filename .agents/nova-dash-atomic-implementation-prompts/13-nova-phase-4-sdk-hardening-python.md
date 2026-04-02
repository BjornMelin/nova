---
prompt_type: "atomic_execution"
model: "gpt-5.4-high"
phase: 4
repo: "nova"
repo_root: "/home/bjorn/repos/work/infra-stack/nova"
suggested_branch: "major/nova-phase-4-sdk-hardening-python"
suggested_commit: "refactor(sdk-py): thin orchestration and minimize custom generator overrides"
self_contained: true
---

# Nova Phase 4 — SDK hardening (Python)

This prompt is self-contained. Do not open sibling prompts for context. Everything needed for this branch is embedded here.

The Python SDK lane is the major remaining Nova-side entropy center. Unlike the TS/R lanes, it is still dominated by one large script and a larger set of committed template/repair choices than the final architecture wants.

## Load these skills before you edit

- `$nova-default-mode` — Use as the orchestration layer. Follow repo truth, hard-cut posture, full doc sync, and repo-native verification.
- `$reducing-entropy` — Deletion-first mindset. Load the `data-over-abstractions` reference before editing and state the principle you are applying in your first progress update.
- `$clean-code` — Keep names intention-revealing, functions small, and modules cohesive. Prefer explicit over clever.

## MCP / tool routing (use if available)

- Local repo inspection first: `rg`, `git grep`, `git status`, `git diff`, targeted test runs, and direct file reads.
- `context7` for official docs only when local repo authority is insufficient, especially for FastAPI, HTTPX, openapi-python-client, and @hey-api/openapi-ts.
- AWS MCP / AWS docs search when infrastructure, deployment, OIDC CI, API Gateway, Step Functions, Lambda, CloudFront, WAF, or runtime guidance is touched.
- GitHub / `gh_grep` only for upstream generator or library behavior when official docs are unclear. Do not use GitHub search to override repo-local truth.
- Zen / architecture review tools only for a final sanity pass on large diffs or when you need a structured review after implementation.

## Embedded toolchain and quality rules

- Use `uv` for environment sync and all Python commands. Do not use pip, poetry, or ad-hoc virtualenv flows.
- Keep Python syntax parseable on Python 3.11. Use the repo-native quality stack: Ruff, ty, mypy, pytest, and the repo-native split pytest lanes.
- Do not reintroduce retired Nova surfaces: session/same-origin auth, `/v1/jobs`, generic job semantics, Redis correctness, ECS/Fargate primary runtime, Lambda Web Adapter public runtime, or split TS SDK package roots.
- If behavior, contracts, generated outputs, release flow, or docs change, update the corresponding docs and tests in the same branch.

## Mission

Turn the Python SDK lane into a thin, generator-owned path while preserving the public package contract and deterministic `--check` behavior. The desired end state is `python_sdk.py` for language-specific logic, a much thinner orchestration CLI, and the smallest unavoidable template/repair surface.

## Decisions already made — do not reopen

- Keep `openapi-python-client==0.28.3` unless current evidence in the repo proves a required upgrade. Do not opportunistically upgrade.
- Keep the public package name `nova-sdk-py` unchanged.
- The generator should own default behavior; repo code should exist only for unavoidable public-package contract shaping.
- This branch does not touch Dash PCA directly, but its output is intended to enable later Dash adoption of `nova-sdk-py`.

**NOTE:** Read and map the more detailed descriptions and alternatives weighed for these decisions in `/home/bjorn/repos/work/infra-stack/nova/.agents/nova-dash-atomic-implementation-prompts/00-decision-framework-scores.md`.

## Preconditions and branch sequencing

- Base from up-to-date `main` in the Nova repo.
- This branch can run in parallel with TS/R cleanup after Nova Phase 1 is merged.
- Dash migration to the public Python SDK should wait until this branch is merged.

## Prioritized findings

### R-001

- **Severity:** [P1]
- **Tag:** Nova-only
- **Area:** Generator ownership
- **One-line finding title:** the Python SDK lane is still monolithic and more repo-owned than the already-thinned TS/R lanes.

**Evidence:**

- `/home/bjorn/repos/work/infra-stack/nova/scripts/release/generate_python_clients.py` is still large and owns language-specific behavior end to end.
- There is no `python_sdk.py` companion in the reviewed snapshot.
- `/home/bjorn/repos/work/infra-stack/nova/scripts/release/generate_clients.py:1-42` already shows the thinner orchestration pattern the Python lane should follow.

**Why it matters**

- This is the biggest remaining Nova-side entropy center after the bridge/runtime cuts.
- Dash should ultimately consume `nova-sdk-py`, not keep a bespoke requests-based adapter forever.

**Fix proposal**

- Add `/home/bjorn/repos/work/infra-stack/nova/scripts/release/python_sdk.py` and shrink `generate_python_clients.py` to orchestration-only responsibilities.
- Estimated delta: **medium-to-high**.
- Risk of partial implementation: the lane stays harder to maintain and harder for downstream consumers to trust.

**Merge blocker?** YES — because downstream SDK adoption depends on this lane being a real public surface.

### R-002

- **Severity:** [P1]
- **Tag:** Nova-only
- **Area:** Template and repair minimization
- **One-line finding title:** committed templates and repair code need a final audit so only unavoidable deviations from upstream generator output remain.

**Evidence:**

- `/home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/` contains committed template overrides.
- `/home/bjorn/repos/work/infra-stack/nova/scripts/release/tests/test_generate_python_clients.py` currently guards the Python generator path.

**Why it matters**

- Excess overrides lock the repo into repo-owned output shape decisions.
- The hard-cut goal is generator-owned output with the minimum unavoidable repo customization.

**Fix proposal**

- Retain only the minimal template overrides that are still necessary for the public package contract.
- Delete repair code that only recreates upstream defaults or legacy output choices.
- Estimated delta: **medium**.
- Risk of partial implementation: the repo will carry a hidden second generator inside its repair layer.

**Merge blocker?** YES — because this is the central unfinished SDK lane.

## Scope

- Python SDK generation orchestration and template/repair minimization.
- Python SDK lane tests and README only where needed to reflect the final minimal override surface.

## Non-goals / out of scope

- Do not alter TypeScript or R generation beyond shared lint/docs fallout.
- Do not rename the public package.
- Do not hand-edit generated SDK output as the primary fix.

## Hard constraints

- Use `uv` and repo-native generation checks.
- Keep Python syntax parseable on Python 3.11.
- If third-party typing issues appear, scope any ignores tightly and prefer actual stubs or local protocol types over broad ignore settings.
- Prefer deleting unnecessary code to wrapping it in more abstractions.

## Required context to read before editing

- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/generate_python_clients.py`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/generate_python_clients.py)
- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/tests/test_generate_python_clients.py`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/tests/test_generate_python_clients.py)
- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/client.py.jinja`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/client.py.jinja)
- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/endpoint_module.py.jinja`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/endpoint_module.py.jinja)
- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/errors.py.jinja`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/errors.py.jinja)
- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/types.py.jinja`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/types.py.jinja)
- [`/home/bjorn/repos/work/infra-stack/nova/packages/nova_sdk_py/README.md`](file:///home/bjorn/repos/work/infra-stack/nova/packages/nova_sdk_py/README.md)

## Target files

- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/python_sdk.py`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/python_sdk.py)
- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/generate_python_clients.py`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/generate_python_clients.py)
- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/tests/test_generate_python_clients.py`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/tests/test_generate_python_clients.py)
- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/client.py.jinja`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/client.py.jinja)
- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/endpoint_module.py.jinja`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/endpoint_module.py.jinja)
- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/errors.py.jinja`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/errors.py.jinja)
- [`/home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/types.py.jinja`](file:///home/bjorn/repos/work/infra-stack/nova/scripts/release/openapi_python_client/templates/types.py.jinja)
- [`/home/bjorn/repos/work/infra-stack/nova/packages/nova_sdk_py/README.md`](file:///home/bjorn/repos/work/infra-stack/nova/packages/nova_sdk_py/README.md)

## Branch bootstrap

```bash
cd /home/bjorn/repos/work/infra-stack/nova
git fetch origin
git switch main
git pull --ff-only
git switch -c major/nova-phase-4-sdk-hardening-python
```

## Detailed implementation steps

1. [x] Inventory the responsibilities currently held inside `generate_python_clients.py`.
   Notes:
   - Orchestration now identified as CLI arg parsing, target iteration, and stale-artifact reporting.
   - Generator-specific logic identified as public-spec filtering/pruning, generator asset validation, `openapi-python-client` invocation, and tree sync/check.
   - Output-repair logic identified as Python-only contract shaping for typed map parsing and presigned URL repr handling; docstring rewrites, relative-import rewrites, and package-init normalization were classified as removable repo-owned noise.
2. [x] Create `scripts/release/python_sdk.py` and move the language-specific generation behavior there.
   Notes:
   - `scripts/release/python_sdk.py` now owns the Python lane implementation.
   - `scripts/release/generate_python_clients.py` is now a thin 49-line CLI/orchestrator that delegates to `generate_or_check_python_sdks(check=...)`.
3. [x] Audit each committed Jinja override.
   Notes:
   - Retained templates: `client.py.jinja`, `endpoint_module.py.jinja`, `errors.py.jinja`, `types.py.jinja`.
   - Removed templates: none.
   - Reason none were deleted: each remaining override still preserves a current public package contract validated by generated-client smoke tests.
   - `client.py.jinja`: preserves immutable builder semantics for materialized clients and auth-header cache reset behavior.
   - `endpoint_module.py.jinja`: preserves raw integer `Response.status_code` behavior for non-IANA codes.
   - `errors.py.jinja`: preserves non-leaking `UnexpectedStatus` stringification without response-body disclosure.
   - `types.py.jinja`: keeps `Response.status_code` typed as `int` instead of upstream `HTTPStatus`.
4. [x] Audit repair/post-processing functions in the same way.
   Notes:
   - Retained repairs:
     - typed `additional_properties` coercion for `metrics_summary_response_activity`, `metrics_summary_response_counters`, `metrics_summary_response_latencies_ms`, `readiness_response_checks`, and `sign_parts_response_urls`
     - repr redaction for `PresignDownloadResponse.url`
   - Removed repairs:
     - `ExportResource.output` parser rewrite
     - relative-import rewriting
     - package `__init__.py` normalization and `# ruff: noqa: I001` injection
     - docstring replacement rewrites
   - Reason retained repairs remain: they are the remaining unavoidable public-package contract shapers after upstream generation plus repo Ruff normalization.
5. [x] Update the lane tests so they assert the final minimal override set and the public package contract.
   Notes:
   - `scripts/release/tests/test_generate_python_clients.py` now imports from `scripts.release.python_sdk`.
   - Tests now assert the retained template set and the retained repair surface instead of deleted repair layers.
6. [x] Update the Python SDK README only if it still overstates customization or omits the final generation entrypoint shape.
   Notes:
   - `packages/nova_sdk_py/README.md` now documents the thin CLI entrypoint, the new `python_sdk.py` implementation module, and the retained minimal repair surface.
7. [x] Run the generation and test matrix below.
   Notes:
   - No unrelated generator drift required scope expansion.
   - Generated SDK artifacts were regenerated and `--check` determinism was revalidated.

## Verification

```bash
cd /home/bjorn/repos/work/infra-stack/nova
uv sync --locked --all-packages --all-extras --dev
uv run python scripts/release/generate_python_clients.py --check
uv run pytest -q /home/bjorn/repos/work/infra-stack/nova/scripts/release/tests/test_generate_python_clients.py
uv run ruff check .
uv run ruff format . --check
uv run mypy
```

### Verification status

- [x] `uv sync --locked --all-packages --all-extras --dev`
- [x] `uv run python scripts/release/generate_python_clients.py --check`
- [x] `uv run pytest -q /home/bjorn/repos/work/infra-stack/nova/scripts/release/tests/test_generate_python_clients.py`
- [x] `uv run ruff check .`
- [x] `uv run ruff format . --check`
- [x] `uv run mypy`
- [x] Additional confidence check: `uv run pytest -q packages/nova_file_api/tests/test_generated_client_smoke.py`

## Success criteria

- `generate_python_clients.py` is orchestration-only or close to it.
- `python_sdk.py` holds the Python-lane implementation details.
- Only the minimum unavoidable template/repair surface remains committed.
- `nova-sdk-py` name and `--check` determinism remain stable.

## Acceptance proof to return at the end of the session

- Exact new responsibilities of `scripts/release/python_sdk.py`.
- Exact templates retained vs removed.
- Exact repair functions retained vs removed.
- Confirmation that package name and `--check` behavior remain stable.
- Command results with pass/fail status.

### Implementation notes for later reference

- [x] `scripts/release/python_sdk.py` responsibilities finalized:
  - public-spec filtering and component pruning
  - generator asset validation and retained-template-set enforcement
  - `openapi-python-client` invocation
  - retained Python-only repair application
  - repo Ruff normalization
  - generated tree sync/check orchestration
- [x] Package contract remained stable:
  - public package name stays `nova-sdk-py`
  - import package stays `nova_sdk_py`
  - `uv run python scripts/release/generate_python_clients.py --check` passes against committed artifacts
- [x] Success criteria satisfied:
  - `generate_python_clients.py` is orchestration-only
  - `python_sdk.py` holds Python-lane implementation details
  - template/repair surface reduced to the minimum currently evidenced as necessary

## Stop conditions / escalation

- If `openapi-python-client` would need to be upgraded to complete this work, stop and report the exact blocker rather than silently upgrading.
- If a template appears removable but removing it changes the public package contract, keep it and document why.
- If unrelated failures occur in generated artifacts outside this lane, note them explicitly and do not broaden scope.
