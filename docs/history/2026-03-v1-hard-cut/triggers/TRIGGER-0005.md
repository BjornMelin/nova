# TRIGGER-0005

Transition note (2026-03-02): This trigger remains a historical cross-repo
tracker for baseline delivery. It does not define active target-state `/v1/*`
implementation sequencing.

## Purpose

Run `docs/history/2026-03-v1-hard-cut/subplans/SUBPLAN-0005.md` in a fresh Codex session.

## Branch

`feat/subplan-0005-cross-repo-release-tracker`

## Copy/Paste Prompt

```markdown
Execute `docs/history/2026-03-v1-hard-cut/subplans/SUBPLAN-0005.md` end-to-end.

Branch: `feat/subplan-0005-cross-repo-release-tracker`

Scope:
- `docs/history/2026-03-v1-hard-cut/subplans/SUBPLAN-0005.md`
- `FINAL-PLAN.md`
- `~/repos/work/infra-stack/container-craft`
- `~/repos/work/pca-analysis-dash/dash-pca`

Mandatory SKILLS:
- `$fastapi`
- `$api-design-principles`
- `$openapi-spec-generation`
- `$architecture-decision-records`
- `$python-anti-patterns`
- `$python-type-safety`
- `$python-code-style`
- `$python-testing-patterns`
- `$pytest-dev`
- `$uv-package-manager`

Tool instructions:

1. Context7:
- Resolve/query docs for FastAPI, AnyIO, boto3/botocore, and pydantic-settings
  before behavior-affecting changes.

2. Exa:
- Validate latest official guidance for AWS ECS/SQS/DynamoDB/CloudWatch and
  FastAPI runtime operations.
- Prefer domains: `docs.aws.amazon.com`, `fastapi.tiangolo.com`,
  `starlette.io`.

3. OpenSrc (inspect these paths directly):
- `opensrc/repos/github.com/fastapi/fastapi`
- `opensrc/repos/github.com/encode/starlette`
- `opensrc/repos/github.com/agronholm/anyio`
- `opensrc/repos/github.com/boto/boto3`
- `opensrc/repos/github.com/boto/botocore`
- `opensrc/repos/github.com/BjornMelin/oidc-jwt-verifier`

4. gh_grep:
- Use literal pattern search for uncertain implementation details:
  - `run_sync(`
  - `send_message(`
  - `CloudWatchMetrics`
  - `APIRouter(`

Execution requirements:
- Keep checklists and evidence current in:
  - `docs/history/2026-03-v1-hard-cut/subplans/SUBPLAN-0005.md`
  - `FINAL-PLAN.md`
- Keep max line length at 80 for Python source modules.
- Enforce Ruff `D` docstring rules in source modules.
- Never log presigned URLs, tokens, or query signatures.

Quality gates:
- Runtime monorepo:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run mypy`
  - `source .venv/bin/activate && uv run pytest -q`
- `container-craft`:
  - `uv run -- ruff check .`
  - `uv run -- mypy`
  - `uv run -- pytest -q`
- `dash-pca`:
  - `source .venv/bin/activate && uv run ruff check . --fix`
  - `source .venv/bin/activate && uv run ruff format .`
  - `source .venv/bin/activate && uv run pyright`
  - `source .venv/bin/activate && uv run pytest -q`
```
