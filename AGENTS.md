# AGENTS.md (aws-file-transfer-api)

## Scope

Implement only what is described in `docs/plan/PLAN.md` and the current `SUBPLAN-*.md`
being executed.

## Guardrails

- Treat OpenAPI as the contract. Add endpoints via SPECs + ADRs first.
- Keep dependencies lean and maintained.
- Never log presigned URLs or query strings.

## Required quality gates

- `uv run -- ruff check .`
- `uv run -- mypy`
- `uv run -- pytest -q`

## Deployment gates

- health endpoint responds within expected time
- structured logs include request_id
- OpenAPI schema builds and docs publish pipeline runs
