# Executive summary

## Status update (2026-03-16)

- `NOVA-AUDIT-003` and `NOVA-AUDIT-004` are resolved in branch
  `fix/strict-shared-idempotency`.
- `NOVA-AUDIT-001`, `NOVA-AUDIT-002`, and `NOVA-AUDIT-006` are no longer the
  top blockers on current `main`.
- The next highest-priority remaining item is `NOVA-AUDIT-005` ECS IAM and
  secret-surface hardening.
- Treat the rest of this file as the original audit snapshot and read it
  alongside `09_STATUS_UPDATE_2026-03-14.md` and
  `10_STATUS_UPDATE_2026-03-16.md`.

## Production-readiness verdict

**Verdict: not production-ready.**

The current commit set has at least two concrete deploy/runtime failures and one correctness contract failure:

- the worker stack is not runnable as committed;
- the main ECS service stack does not inject the runtime config the application reads;
- distributed idempotency is documented as fail-closed but implemented as local fallback on shared-cache failure.

## Top 10 risks

1. Async worker lane is not deployable from the committed templates/image/runtime contract.
2. Main ECS service ignores documented runtime env via dead `ENV_DICT` indirection.
3. Distributed idempotency correctness is not fail-closed; duplicate mutations are possible during shared-cache failure.
4. Historical audit note: readiness behavior did not match the previously
   documented dependency-scoped health contract.
5. Default ECS task permissions are far too broad for the service footprint.
6. CI reproducibility is already broken by a stale `uv.lock`.
7. Dash bridge violates boundary ownership and duplicates core API models.
8. Dash bridge has zero tests despite owning adapter behavior.
9. Mutation routes duplicate orchestration logic and will drift further on every change.
10. Infra tests currently validate stale strings instead of deployable behavior.

## Top 10 recommended next actions

1. Fix the deployment contract first: service env injection, worker command, worker env names, and secret wiring.
2. Make templates, release scripts, runtime settings, and infra tests derive from one canonical config contract.
3. Finish ECS IAM and secret-surface hardening.
4. Replace remaining textual infra assertions with semantic compatibility tests.
5. Delete legacy `ENV_DICT` and default-broad IAM paths after a short migration window.
6. Regenerate and commit `uv.lock`; re-enable clean locked installs before any other CI work.
7. Refactor `nova_dash_bridge` to depend on a stable public contract instead of `nova_file_api` internals.
8. Add the first bridge tests before further bridge refactors.
9. Extract guarded-mutation workflow logic out of route handlers.
10. Replace textual infra assertions with semantic compatibility tests across image/template/runtime boundaries.

## Most concerning architectural theme

The repo lacks a single executable source of truth for runtime configuration and deployment wiring. Settings aliases, CloudFormation templates, release scripts, docs, and infra tests have drifted into separate realities.

## Most likely failure modes

- worker tasks crash immediately on startup because the command path is wrong and required `JOBS_*` settings are missing
- ECS service boots with default or partial runtime config because `ENV_DICT` is injected but not consumed
- multi-instance mutation endpoints admit duplicates during Redis/shared-cache failures
- historical readiness drift caused failures on non-traffic-critical
  dependencies and noisy deployment health behavior before the active-doc
  reconciliation in this branch
- broad wildcard IAM turns application compromise into a larger AWS blast radius

## What was verified versus only inspected

### Verified in this environment

- `python -m compileall -q packages scripts tests` — Succeeded. Syntax compilation passed for the inspected Python sources in this environment.
- `uv lock --check` — Failed. uv reported that `uv.lock` is out of date relative to project metadata.
- `uv sync --frozen --dev --offline` — Failed. Network is disabled in this environment and the required cached wheel set is incomplete (`redis==7.1.1` missing), so repo-native lint/type/test commands could not be run from a cold cache.

### Inspected statically only

- CloudFormation templates
- Dockerfiles
- GitHub Actions workflows
- Pydantic settings and dependency wiring
- route/service architecture
- docs/spec/ADR/runbook drift
- bridge package coupling
- generated package topology
- release scripts

## Constraints and unknowns

- No live AWS deployment validation was possible here.
- Full repo-native lint/type/test/build execution was not possible because the locked dependencies could not be fully materialized offline.
- Findings are grounded in file evidence and the executed checks above; no unrun command is claimed as run.
