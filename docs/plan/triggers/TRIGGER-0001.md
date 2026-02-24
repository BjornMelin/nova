# TRIGGER-0001

## Purpose

Run `docs/plan/subplans/SUBPLAN-0001.md` in a fresh Codex session.

## Branch

`feat/subplan-0001-core-runtime-contract-hardening`

## Copy/Paste Prompt

```markdown
Execute `docs/plan/subplans/SUBPLAN-0001.md` end-to-end.

Branch: `feat/subplan-0001-core-runtime-contract-hardening`

Primary files:
- `docs/plan/subplans/SUBPLAN-0001.md`
- `docs/plan/PLAN.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`

Mandatory SKILLS:
- `$fastapi`
- `$api-design-principles`
- `$openapi-spec-generation`
- `$python-anti-patterns`
- `$python-code-style`
- `$python-type-safety`
- `$python-testing-patterns`
- `$pytest-dev`
- `$uv-package-manager`

Tool instructions:

1. Context7:
- Resolve and query docs before contract/runtime changes:
  - FastAPI
  - AnyIO
  - pydantic-settings

2. web.run:
- Validate official sources for FastAPI lifecycle/deployment and standards.
- Prefer domains: `fastapi.tiangolo.com`, `docs.pydantic.dev`,
  `datatracker.ietf.org`.

3. OpenSrc (inspect these paths directly):
- `opensrc/repos/github.com/fastapi/fastapi`
- `opensrc/repos/github.com/pydantic/pydantic`
- `opensrc/repos/github.com/pydantic/pydantic-settings`
- `opensrc/repos/github.com/Kludex/uvicorn`
- `opensrc/repos/github.com/BjornMelin/oidc-jwt-verifier`

4. gh_grep:
- Use literal code pattern search when implementation details are ambiguous,
  e.g. `APIRouter(`, `asynccontextmanager`, `to_thread.run_sync`.

Execution requirements:
- Implement subplan tasks fully.
- Keep max line length at 80 and enforce Ruff `D` docstring rules in source.
- Never log presigned URLs or query signatures.
- Update `docs/plan/PLAN.md` progress as work completes.

Quality gates (required):
- `source .venv/bin/activate && \
  uv run ruff check . --fix && \
  uv run ruff format .`
- `source .venv/bin/activate && \
  uv run mypy`
- `source .venv/bin/activate && \
  uv run pytest -q`
```
