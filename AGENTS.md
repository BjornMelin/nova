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

<!-- opensrc:start -->

## Source Code Reference

Source code for dependencies is available in `opensrc/` for deeper understanding of implementation details.

See `opensrc/sources.json` for the list of available packages and their versions.

Use this source code when you need to understand how a package works internally, not just its types/interface.

### Fetching Additional Source Code

To fetch source code for a package or repository you need to understand, run:

```bash
npx opensrc <package>           # npm package (e.g., npx opensrc zod)
npx opensrc pypi:<package>      # Python package (e.g., npx opensrc pypi:requests)
npx opensrc crates:<package>    # Rust crate (e.g., npx opensrc crates:serde)
npx opensrc <owner>/<repo>      # GitHub repo (e.g., npx opensrc vercel/ai)
```

<!-- opensrc:end -->