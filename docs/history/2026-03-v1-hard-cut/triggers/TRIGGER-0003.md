# TRIGGER-0003

Transition note (2026-03-02): This trigger is retained as baseline migration
evidence. `container-craft` scope references are historical and not active
deployment authority for Nova.

## Purpose

Run `docs/history/2026-03-v1-hard-cut/subplans/SUBPLAN-0003.md` in a fresh Codex session.

## Branch

`feat/subplan-0003-infra-cross-repo-integration`

## Copy/Paste Prompt

```markdown
Execute `docs/history/2026-03-v1-hard-cut/subplans/SUBPLAN-0003.md` end-to-end.

Branch: `feat/subplan-0003-infra-cross-repo-integration`

Scope:
- `packages/nova_file_api`
- `packages/nova_auth_api`
- `packages/nova_file_api`
- `packages/nova_auth_api`
- `packages/nova_dash_bridge`
- `packages/contracts`
- `${REPO_INFRA_PATH:-~/repos/work/infra-stack/container-craft}`
- `${REPO_DASH_PATH:-~/repos/work/pca-analysis-dash/dash-pca}`

Mandatory SKILLS:
- `$fastapi`
- `$api-design-principles`
- `$python-anti-patterns`
- `$python-observability`
- `$python-resilience`
- `$python-code-style`
- `$uv-package-manager`

Tool instructions:

1. Context7:
- Resolve/query docs for boto3/botocore and FastAPI deployment patterns.

2. Exa:
- Validate AWS operational guidance (ECS health checks, S3 acceleration,
  presigned URL guardrails, CloudWatch).
- Prefer domain: `docs.aws.amazon.com`.

3. OpenSrc (inspect these paths directly):
- `opensrc/repos/github.com/boto/boto3`
- `opensrc/repos/github.com/boto/botocore`
- `opensrc/repos/github.com/fastapi/fastapi`

4. gh_grep:
- Search real-world patterns for `use_accelerate_endpoint`,
  `target-group-health-checks`, `send_message(`.

Execution requirements:
- Align infra contracts and runtime config.
- Validate env mapping for:
  - `JOBS_SQS_RETRY_MODE`
  - `JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS`
  - startup validation dependencies for SQS and DynamoDB backends
- Update docs/spec/plan artifacts to reflect validated infra decisions.
- Track unresolved infra blockers explicitly in `docs/plan/PLAN.md`.

Quality gates for this repo after touching code:
- `source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .`
- `source .venv/bin/activate && uv run mypy`
- `source .venv/bin/activate && uv run pytest -q`
```
