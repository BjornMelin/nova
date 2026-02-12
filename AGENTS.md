# AGENTS.md (aws-file-transfer-api)

## SKILLS AND TOOLS

### SKILLS

**SKILLS TO USE WHILE WORKING ON THIS REPOSITORY (ALWAYS LOAD THE RIGHT SKILL)**:

- $fastapi : Build FastAPI APIs with Pydantic v2 and async patterns, including validation, auth, DB integration, and common failure prevention.
- $openapi-spec-generation : Design and maintain OpenAPI 3.1 contracts, validation, and spec-first API workflows.
- $architecture-decision-records : Write clear ADRs for major technical decisions with strong rationale and tradeoffs.
- $api-design-principles : Apply REST API design best practices for consistent, intuitive, and maintainable endpoints.
- $python-type-safety : Enforce strong typing with type hints, protocols, and strict checker-friendly design.
- $python-code-style : Keep Python code clean, consistent, linted, formatted, and maintainable.
- $python-testing-patterns : Build robust pytest suites with solid fixtures, mocking, and test strategy.
- $pytest-dev : Advanced pytest optimization, flake reduction, coverage improvement, and CI test performance.
- $uv-package-manager : Use uv effectively for env setup, dependency management, and reproducible Python workflows.

### TOOLS

**TOOLS TO USE WHILE WORKING ON THIS REPOSITORY (ALWAYS LOAD THE RIGHT TOOL)**:

### Library docs (Context7)

- context7.resolve-library-id: map a library/package name to a Context7-compatible library ID
- context7.query-docs: query up-to-date docs/snippets for a specific Context7 library ID

### Real‑world code examples

- gh_grep.searchGitHub — Search GitHub code for literal patterns; use when API usage is unclear or you want production examples.

---

### Web research (Exa)

- exa.web_search_advanced_exa: advanced web search with filters (domains/dates/category), summaries/highlights, and content options.
- exa.deep_researcher_start: Start an AI research agent that searches, reads, and writes a detailed report (returns a task ID).
  - ALWAYS wait for it to finish and return the research report before continuing with any other work.
- exa.deep_researcher_check: Check status and retrieve the report for a deep research task.

---

### PLANNING & RESOURCES

- functions.update_plan: Maintain a live multi‑step plan.

---

### DEEP SOURCE INSPECTION (OPENSRC CLI)

When documentation is ambiguous or you need to understand "under-the-hood" logic:

- Run `opensrc list` to view all of the libraries we have access to and search and explore them at the paths provided in the `opensrc list` output when we
need to use a library to ensure that we are using their latest advanced capabilities, correct api references and full typing.

---

### Operational Mandate

Do not oversimplify or defer features. Use the tools above to converge on the best SOTA solution. If sources conflict, use the decision framework and
ensure the chosen option scores at least 9.0/10.0. Every line of documentation and code must be production‑ready and reflect a "production-ready", "final-release" standard.

## Guardrails

- Work off the PLAN.md file and track the progress of the plan in the PLAN.md file.
- Treat OpenAPI as the contract. Add endpoints via SPECs + ADRs first.
- Keep dependencies lean and maintained.
- Never log presigned URLs or query strings.

## Required quality gates

**ALWAYS** run all commands in the virtual environment prefixed with `source .venv/bin/activate &&`.

- `uv run ruff check . --fix && uv run ruff format .`
- `uv run mypy`
- `uv run pytest -q`

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
