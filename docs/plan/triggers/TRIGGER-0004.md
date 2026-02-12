# TRIGGER-0004

## Purpose

Run `docs/plan/subplans/SUBPLAN-0004.md` in a fresh Codex session.

## Branch

`feat/subplan-0004-e2e-validation-release-closure`

## Copy/Paste Prompt

```markdown
Execute `docs/plan/subplans/SUBPLAN-0004.md` end-to-end.

Branch: `feat/subplan-0004-e2e-validation-release-closure`

Scope:
- `apps/aws_file_api_service`
- `apps/aws_auth_api_service`
- `packages/aws_file_api`
- `packages/aws_auth_api`
- `packages/aws_dash_bridge`
- `packages/contracts`
- `~/repos/work/infra-stack/container-craft`
- `~/repos/work/pca-analysis-dash/dash-pca`

Mandatory SKILLS:
- `$fastapi`
- `$api-design-principles`
- `$python-anti-patterns`
- `$python-testing-patterns`
- `$pytest-dev`
- `$python-observability`
- `$python-resilience`
- `$python-code-style`
- `$uv-package-manager`

Tool instructions:

1. Context7:
- Re-check FastAPI/OpenAPI and dependency docs for version-sensitive behavior.

2. Exa:
- Validate latest AWS docs for final release gates and alarm/dashboard guidance.
- Prefer domain: `docs.aws.amazon.com`.

3. OpenSrc (inspect these paths directly):
- `opensrc/repos/github.com/fastapi/fastapi`
- `opensrc/repos/github.com/boto/boto3`
- `opensrc/repos/github.com/boto/botocore`
- `opensrc/repos/github.com/BjornMelin/oidc-jwt-verifier`

4. gh_grep:
- Use literal code pattern search to verify real-world examples for E2E
  operational checks.

Execution requirements:
- Produce evidence for contract/auth/async/cache/observability acceptance checks.
- Include explicit evidence for:
  - enqueue publish-failure response contract (`503 queue_unavailable`)
  - idempotency behavior after failed enqueue attempts (no success replay)
  - readiness behavior with optional features disabled
- Update final checkboxes and progress log in `docs/plan/PLAN.md`.
- Document remaining risks with explicit mitigations.

Quality gates (required in this repo when code changes):
- `source .venv/bin/activate && uv run ruff check . --fix && uv run ruff format .`
- `source .venv/bin/activate && uv run mypy`
- `source .venv/bin/activate && uv run pytest -q`
```
