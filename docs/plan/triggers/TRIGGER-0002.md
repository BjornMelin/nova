# TRIGGER-0002

## Purpose

Run `docs/plan/subplans/SUBPLAN-0002.md` in a fresh Codex session.

## Branch

`feat/subplan-0002-async-cache-observability-completion`

## Copy/Paste Prompt

```markdown
Execute `docs/plan/subplans/SUBPLAN-0002.md` end-to-end.

Branch: `feat/subplan-0002-async-cache-observability-completion`

Primary files:
- `docs/plan/subplans/SUBPLAN-0002.md`
- `docs/plan/PLAN.md`
- `docs/architecture/adr/ADR-0010-enqueue-failure-and-readiness-semantics.md`
- `docs/architecture/spec/SPEC-0008-async-jobs-and-worker-orchestration.md`
- `docs/architecture/spec/SPEC-0009-caching-and-idempotency.md`
- `docs/architecture/spec/SPEC-0010-observability-analytics-and-activity-rollups.md`

Mandatory SKILLS:
- `$fastapi`
- `$api-design-principles`
- `$python-anti-patterns`
- `$python-background-jobs`
- `$async-python-patterns`
- `$python-observability`
- `$python-performance-optimization`
- `$python-resilience`
- `$python-code-style`
- `$python-type-safety`
- `$python-testing-patterns`
- `$pytest-dev`
- `$uv-package-manager`

Tool instructions:

1. Context7:
- Resolve/query docs for AnyIO, FastAPI, and pydantic-settings before behavior
  changes.

2. Exa:
- Validate official AWS guidance for EMF/cardinality and cache/queue patterns.
- Prefer domains: `docs.aws.amazon.com`, `fastapi.tiangolo.com`.

3. OpenSrc (inspect these paths directly):
- `opensrc/repos/github.com/fastapi/fastapi`
- `opensrc/repos/github.com/pydantic/pydantic`
- `opensrc/repos/github.com/pydantic/pydantic-settings`
- `opensrc/repos/github.com/boto/boto3`
- `opensrc/repos/github.com/boto/botocore`
- `opensrc/repos/github.com/BjornMelin/oidc-jwt-verifier`

4. gh_grep:
- Use pattern-based searches for real-world usage,
  e.g. `send_message(`, `generate_presigned_url(`, `CloudWatchMetrics`.

Execution requirements:
- Complete all subplan items.
- Extend tests for async/caching/observability behaviors.
- Verify `jobs/enqueue` publish-failure semantics:
  - `503` + `error.code = "queue_unavailable"`
  - no success idempotency replay cache on failed enqueue
- Verify `/readyz` excludes feature-flag pass/fail coupling.
- Update `docs/plan/PLAN.md` completion status.

Quality gates (required):
- `source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .`
- `source .venv/bin/activate && uv run mypy`
- `source .venv/bin/activate && uv run pytest -q`
```
