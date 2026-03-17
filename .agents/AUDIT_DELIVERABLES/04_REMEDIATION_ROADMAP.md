# Remediation roadmap

## Executive remediation thesis

Do **not** start with cosmetic refactors. The first job is to make the deployable artifact chain truthful:

`runtime settings -> release automation -> CloudFormation task definitions -> container entrypoint/env -> runtime startup`

Until that chain is fixed, the repo’s docs, tests, and workflows will continue to produce false confidence.

## Root-cause clusters

### Cluster A — Runtime configuration contract is fragmented

Included findings:

- NOVA-AUDIT-001
- NOVA-AUDIT-002
- NOVA-AUDIT-004
- NOVA-AUDIT-010

### Cluster B — Production correctness semantics are weaker than promised

Included findings:

- NOVA-AUDIT-003
- NOVA-AUDIT-004
- NOVA-AUDIT-009

### Cluster C — Security posture retained migration defaults

Included findings:

- NOVA-AUDIT-005

### Cluster D — Adapter boundary has decayed

Included findings:

- NOVA-AUDIT-007
- NOVA-AUDIT-008
- NOVA-AUDIT-011

### Cluster E — Toolchain gates are not trustworthy enough yet

Included findings:

- NOVA-AUDIT-006
- NOVA-AUDIT-012

## Phase 1: Immediate stabilization

### Goal

Make the shipped runtime deployable, reproducible, and minimally trustworthy.

### Batches

#### Batch 1 — Align service and worker deployment wiring with runtime settings

- **Why it belongs together:** same broken contract across settings, templates, release script, and tests
- **Included findings:** NOVA-AUDIT-001, NOVA-AUDIT-002, NOVA-AUDIT-010
- **Expected risk reduction:** very high
- **Likely files/systems affected:** `infra/runtime/ecs/service.yml`, `infra/runtime/file_transfer/worker.yml`, `scripts/release/deploy-runtime-cloudformation-environment.sh`, `tests/infra/**`, `packages/nova_file_api/src/nova_file_api/config.py`
- **Validation gates:** rendered task-definition parity tests; worker image entrypoint check; startup smoke
- **Rollout risks:** breaking undocumented legacy deploy habits
- **Suggested branch:** `fix/runtime-config-contract`
- **Suggested PR title:** `fix: align ecs service and worker templates with canonical runtime settings`

#### Batch 2 — Restore locked reproducibility

- **Why it belongs together:** CI cannot be trusted while the lockfile is stale
- **Included findings:** NOVA-AUDIT-006
- **Expected risk reduction:** high for CI hygiene; low for runtime directly
- **Likely files/systems affected:** `uv.lock`, `pyproject.toml`, CI docs
- **Validation gates:** `uv lock --check`; `uv sync --locked`
- **Rollout risks:** exposes new dependency conflicts
- **Suggested branch:** `chore/refresh-uv-lock`
- **Suggested PR title:** `chore: regenerate uv lockfile and restore locked installs`

#### Batch 3 — Completed 2026-03-17: remove broad default task permissions and finish secret wiring migration

- **Why it belonged together:** same template default posture
- **Included findings:** NOVA-AUDIT-005
- **Expected risk reduction:** delivered high security benefit
- **Likely files/systems affected:** `infra/runtime/ecs/service.yml`, `scripts/release/deploy-runtime-cloudformation-environment.sh`, `tests/infra/**`, active docs/runbooks, live audit trackers
- **Validation gates:** focused infra contract tests, CFN lint, script syntax, `uv lock --check`
- **Rollout risks:** residual deploy smoke in AWS is still recommended to confirm no hidden permission edges
- **Implemented branch:** `feat/repo-managed-ecs-task-role`
- **Implemented PR title:** `hardening: repo-manage ecs service task role and remove legacy secret shims`

## Phase 2: Correctness and architecture hardening

### Goal

Make the runtime semantics match the repo’s published contract and reduce future drift.

#### Batch 4 — Implement explicit idempotency mode and fail-closed production semantics

- **Why it belongs together:** shared-store failure semantics, readiness, and tests are one design surface
- **Included findings:** NOVA-AUDIT-003, NOVA-AUDIT-004
- **Expected risk reduction:** very high correctness gain
- **Likely files/systems affected:** `packages/nova_file_api/src/nova_file_api/config.py`, `cache.py`, `idempotency.py`, `routes/platform.py`, tests, docs/specs
- **Validation gates:** mode-aware unit/integration tests; failure-injection tests
- **Rollout risks:** lower availability during shared-cache outage in prod mode
- **Suggested branch:** `fix/idempotency-shared-required`
- **Suggested PR title:** `fix: implement shared-required idempotency and readiness semantics`

#### Batch 5 — Re-establish the bridge as an adapter instead of a contract fork

- **Why it belongs together:** dependency inversion, model dedupe, and adapter tests all support the same boundary
- **Included findings:** NOVA-AUDIT-007, NOVA-AUDIT-008, NOVA-AUDIT-011
- **Expected risk reduction:** high maintainability gain
- **Likely files/systems affected:** `packages/nova_dash_bridge/**`, selected public contract surfaces in `nova_file_api` or generated SDK usage
- **Validation gates:** architectural import test; bridge adapter tests; contract smoke tests
- **Rollout risks:** public Python adapter consumers may need migration notes
- **Suggested branch:** `refactor/dash-bridge-boundary`
- **Suggested PR title:** `refactor: make nova_dash_bridge consume a stable public contract`

#### Batch 6 — Extract guarded mutation workflow from route handlers

- **Why it belongs together:** removes the duplicated request lifecycle logic that currently sprawls across routes
- **Included findings:** NOVA-AUDIT-009
- **Expected risk reduction:** medium-high maintainability gain
- **Likely files/systems affected:** `routes/transfers.py`, `routes/jobs.py`, new service/workflow module, tests
- **Validation gates:** route integration parity tests; direct workflow unit tests
- **Rollout risks:** accidental behavior drift if abstraction is too broad
- **Suggested branch:** `refactor/guarded-mutation-workflow`
- **Suggested PR title:** `refactor: centralize idempotent mutation workflow for file and job routes`

## Phase 3: Performance, DX, docs, and cleanup

### Goal

Make the repo cheaper to operate and less likely to drift again.

#### Batch 7 — Harden CI and test import behavior

- **Why it belongs together:** both reduce clean-environment flakiness
- **Included findings:** NOVA-AUDIT-012
- **Expected risk reduction:** medium
- **Likely files/systems affected:** `pyproject.toml`, `.github/workflows/ci.yml`, `.github/actions/setup-python-uv/action.yml`
- **Validation gates:** clean-cache CI run; pytest collection under importlib mode
- **Rollout risks:** import issues become visible
- **Suggested branch:** `chore/ci-uv-pytest-hardening`
- **Suggested PR title:** `chore: pin uv, enable cache management, and move pytest toward importlib mode`

#### Batch 8 — Repair docs and runbooks after code/template truth is restored

- **Why it belongs together:** docs should reflect enforced behavior, not aspirational behavior
- **Included findings:** affects NOVA-AUDIT-001 through NOVA-AUDIT-005 and NOVA-AUDIT-010
- **Expected risk reduction:** medium
- **Likely files/systems affected:** `README.md`, `docs/architecture/spec/**`, `docs/plan/**`, `docs/runbooks/**`
- **Validation gates:** docs-vs-contract checks; reviewed operator examples
- **Rollout risks:** none beyond review overhead
- **Suggested branch:** `docs/runtime-contract-reconciliation`
- **Suggested PR title:** `docs: reconcile runtime configuration and worker deployment guidance`

#### Batch 9 — Add machine-readable config contract generation

- **Why it belongs together:** this is the durable fix for repeated drift
- **Included findings:** root-cause fix across multiple findings
- **Expected risk reduction:** high long-term
- **Likely files/systems affected:** config schema generation code, template tests, docs generation
- **Validation gates:** generated env matrix checked into CI; template parity tests
- **Rollout risks:** moderate design effort
- **Suggested branch:** `build/config-contract-matrix`
- **Suggested PR title:** `build: generate canonical runtime configuration contract for code, templates, and docs`

#### Batch 10 — Add layered architecture enforcement tests

- **Why it belongs together:** the repo already documents boundaries; now enforce them
- **Included findings:** NOVA-AUDIT-007, NOVA-AUDIT-010
- **Expected risk reduction:** medium-high
- **Likely files/systems affected:** tests, maybe a small import-rule helper
- **Validation gates:** CI import-graph tests; contract boundary tests
- **Rollout risks:** existing violations become visible immediately
- **Suggested branch:** `test/enforce-component-boundaries`
- **Suggested PR title:** `test: enforce runtime package boundaries and template compatibility contracts`

## Dependency ordering between fixes

1. Batch 1 before everything else.
2. Batch 2 can happen in parallel with Batch 1, but should merge early.
3. Batch 3 should land once Batch 1 clarifies the canonical env/secrets path.
4. Batch 4 depends on Batch 1 because the runtime has to receive the correct cache/config vars first.
5. Batch 5 can start after Batch 1; it benefits from a stable runtime contract.
6. Batch 6 should follow Batch 4 so the extracted workflow captures the corrected semantics.
7. Batches 7–10 should follow once the runtime contract is stable enough to encode.

## Anti-plan: what should explicitly NOT be done yet

- Do **not** begin a broad monorepo reorganization first.
- Do **not** replace core libraries for fashion reasons.
- Do **not** spend a sprint polishing docs before the templates and runtime are truthful.
- Do **not** add more infra string tests; add semantic compatibility tests instead.
- Do **not** treat the bridge refactor as a pure packaging exercise; its problem is boundary ownership, not just layout.

## Top 10 implementation batches

1. Align service and worker deployment wiring with runtime settings
2. Restore locked reproducibility
3. Remove broad default task permissions and finish secret wiring migration
4. Implement explicit idempotency mode and fail-closed production semantics
5. Re-establish the bridge as an adapter instead of a contract fork
6. Extract guarded mutation workflow from route handlers
7. Harden CI and test import behavior
8. Repair docs and runbooks after code/template truth is restored
9. Add machine-readable config contract generation
10. Add layered architecture enforcement tests
