

<!-- FILE: README.md -->

# Nova Codex remediation prompt pack

This pack converts the architecture review into an execution program for **separate Codex `gpt-5.4-high` sessions**. The prompts are intentionally opinionated and hard-cut: they are designed to land the best production-ready end state, not a minimally disruptive migration.

## Included artifacts

- `ISSUE_REGISTER.md` — stable issue IDs and dependency context.
- `FILE_IMPACT_MAP.md` — prompt-to-file mapping.
- `PROMPT_ISSUE_MATRIX.md` — issue-to-prompt ownership and verification map.
- `prompts/01-...md` through `prompts/05-...md` — implementation sessions.
- `prompts/99-final-critical-review-and-finish.md` — final verification and cleanup session.

## Recommended execution order

1. `prompts/01-public-ingress-hard-cut.md`
2. `prompts/02-runtime-simplification-cors-auth.md`
3. `prompts/03-runtime-deploy-oidc-provenance.md`
4. `prompts/04-security-observability-capacity-iam.md` — completed in branch; live dev AWS rollout blocked by external Lambda concurrency quota
5. `prompts/05-validation-tests-docs-authority-cleanup.md`
6. `prompts/99-final-critical-review-and-finish.md`

Run them **sequentially**. Each later prompt assumes the previous prompt’s changes are present.

## Branching / orchestration recommendation

- Preferred: a single remediation branch with one Codex session per prompt and one commit series.
- Also acceptable: stacked branches (`prompt-01` -> `prompt-02` -> …) if your review process prefers smaller diffs.
- Do not run the prompts in parallel against the same branch unless you have an explicit merge/conflict plan.

## Subagent recommendation

If your Codex environment supports concurrent helper agents, create a few narrow `gpt-5.4-mini` subagents in each session. Good defaults:
- one for **official-doc research**,
- one for **repo file impact and hidden coupled contracts**,
- one for **tests / validation / docs authority drift**.

Make the main `gpt-5.4-high` session reconcile those outputs before coding.

## Notes

- These prompts were prepared from the locally extracted `nova-release-rebaseline.zip` archive and `PR-96.diff` already present in the workspace.
- Some original uploaded file handles expired at the platform layer, so if you want a brand-new file-tool-based reinspection later, re-uploading is useful. The local copies used for this pack were still available.


<!-- FILE: ISSUE_REGISTER.md -->

# Issue register used across all prompts

Use these stable issue IDs in every Codex session. Treat them as the required acceptance contract for the remediation program.

## [P0] Merge blockers

- **P0-1 — Runtime deployment ownership deleted without replacement.** Completed by Prompt 03. The repo now owns runtime deployment again through GitHub Actions reusable workflows, AWS OIDC, and immutable release-built runtime artifacts.
- **P0-2 — Current CloudFront API edge cannot serve write traffic.** The surviving CloudFront distribution does not explicitly enable write methods, while the API exposes POST-heavy flows.
- **P0-3 — CloudFront/WAF is bypassable.** The API default execute-api endpoint remains reachable directly, so the supposed protected front door is not authoritative.

## [P1] High-severity design and operational defects

- **P1-1 — Browser/downstream integration has no coherent CORS model.** Completed by Prompt 02. FastAPI app CORS, infra allowed origins, and browser-contract tests now form one explicit contract.
- **P1-2 — Wrong AWS ingress product mix.** The current architecture uses HTTP API plus CloudFront/WAF as a compensation layer instead of the simpler and better-fitting Regional REST API plus direct WAF attachment.
- **P1-3 — Abuse prevention is below production state.** Completed by Prompt 04. Regional WAF rate limiting and API Gateway stage throttling are implemented, test-enforced, and deployed live in dev with the low-quota non-prod fallback.
- **P1-4 — Observability and forensics are below production state.** Completed by Prompt 04. API Gateway access logging, WAF logging, and SNS-backed alarm actions are implemented, test-enforced, and deployed live in dev.
- **P1-5 — Docs/specs/runbooks/contracts are internally contradictory.** Completed by Prompts 03 and 05. Prompt 03 fixed the workflow / contract / release-doc half; Prompt 05 finished the broader docs-authority sweep so active routers, specs, runbooks, and contracts now describe one implemented wave-2 platform.

## [P2] Important but non-blocking defects

- **P2-1 — Post-deploy validation is too weak.** Completed by Prompts 03 and 05. Prompt 03 bound validation to deploy-output provenance; Prompt 05 expanded it to prove runtime version/environment truth, protected-route auth behavior, CORS preflight, and disabled execute-api ingress.
- **P2-2 — Workflow Lambdas are over-privileged.** Completed by Prompt 04. Workflow task functions now use task-scoped IAM instead of broad cloned bucket/table grants, and that IAM shape is live in dev.
- **P2-3 — Runtime safeguards are missing.** Completed by Prompt 04. S3 lifecycle cleanup, bounded ingress defaults, and explicit concurrency policy are implemented; low-quota non-prod accounts now omit reserved concurrency intentionally while production remains fail-closed.
- **P2-4 — Tests validate deletions and thin invariants, not production truth.** Completed by Prompt 05. Infra and contract tests now assert ingress truth, deploy-output provenance, docs authority, runtime-config artifact freshness, logging, throttling, IAM, lifecycle, and validation workflow behavior.
- **P2-5 — Runtime path is overcomplicated.** Completed by Prompt 02 plus release-artifact follow-up. The public API now uses native Lambda handling, no Lambda Web Adapter, no uvicorn-in-Lambda, and no synth-time local packaging path.

## [P3] Cleanup debt that should be closed during the hard cut

- **P3-1 — Hard-cut cleanup is incomplete.** Completed by Prompts 02 and 05. Prompt 02 removed the main deprecated aliases and compatibility paths; Prompt 05 finished the dead contract/doc cleanup by deleting template-era runtime-config surfaces and aligning generated artifacts to living Lambda/runtime ownership only.

## There are no meaningful [P4] findings in the current review.



<!-- FILE: PROMPT_ISSUE_MATRIX.md -->

# Prompt to issue matrix

This matrix shows which prompt directly closes each issue and which later prompts verify it.

| Issue ID | Summary | Primary prompt | Secondary / verification prompts | Status |
|---|---|---:|---|---|
| P0-1 | Repo-owned runtime deploy deleted | 03 | 05, 99 | Completed in 03 |
| P0-2 | CloudFront API edge cannot serve write traffic | 01 | 99 | Completed in 01 |
| P0-3 | CloudFront/WAF bypass via default execute-api endpoint | 01 | 99 | Completed in 01 |
| P1-1 | No coherent CORS model | 02 | 05, 99 | Completed in 02 |
| P1-2 | Wrong ingress product mix | 01 | 99 | Completed in 01 |
| P1-3 | Missing abuse prevention | 04 | 05, 99 | Completed in 04 and deployed live in dev |
| P1-4 | Weak observability / forensics | 04 | 03, 05, 99 | Completed in 04 and deployed live in dev |
| P1-5 | Docs/specs/contracts/runbooks contradictory | 05 | 03, 99 | Completed by 03 + 05 |
| P2-1 | Weak post-deploy validation / provenance | 03 | 05, 99 | Completed by 03 + 05 |
| P2-2 | Workflow Lambdas over-privileged | 04 | 99 | Completed in 04 and deployed live in dev |
| P2-3 | Missing reserved concurrency / lifecycle safeguards | 04 | 99 | Completed in 04 with low-quota non-prod fallback live in dev |
| P2-4 | Thin test suite not asserting production truth | 05 | 01, 02, 04, 99 | Completed in 05 |
| P2-5 | Runtime overcomplicated | 02 | 99 | Completed in 02 + packaging follow-up |
| P3-1 | Incomplete hard-cut cleanup | 02 | 05, 99 | Completed in 02 and finalized in 05 |

## Prompt dependency notes

- Prompt 02 assumes Prompt 01 already changed the ingress and stack structure.
- Prompt 03 assumes the runtime has one canonical public base URL from Prompt 01 and a stable runtime path from Prompt 02.
- Prompt 04 assumes the stack structure from Prompt 01 and runtime shape from Prompt 02.
- Prompt 05 assumes Prompts 01-04 have landed so it can rewrite docs/tests/contracts to the final truth instead of another moving target.
- Prompt 99 verifies and fixes everything after all implementation prompts.


<!-- FILE: FILE_IMPACT_MAP.md -->

# File impact map

This is the recommended prompt-to-file ownership map. It is intentionally explicit so each Codex session knows what it must touch.

## Prompt 01 — Public ingress hard cut
Directly owns:
- `infra/nova_cdk/app.py`
- `infra/nova_cdk/README.md`
- `infra/nova_cdk/src/nova_cdk/__init__.py`
- `infra/nova_cdk/src/nova_cdk/serverless_stack.py` (delete or convert to compatibility-free wrapper only if strictly necessary)
- new modular CDK files under `infra/nova_cdk/src/nova_cdk/` such as:
  - `runtime_stack.py`
  - `data_plane.py`
  - `ingress.py` or equivalent
- `tests/infra/test_serverless_stack_contracts.py` (replace or split)
- new infra tests such as:
  - `tests/infra/test_runtime_stack_contracts.py`
  - `tests/infra/test_ingress_contracts.py`
- targeted architecture docs that would otherwise remain false immediately after the ingress change

## Prompt 02 — Runtime simplification, native Lambda handler, CORS, auth cleanup
Directly owns:
- `packages/nova_file_api/pyproject.toml`
- `packages/nova_file_api/src/nova_file_api/app.py`
- `packages/nova_file_api/src/nova_file_api/main.py`
- `packages/nova_file_api/src/nova_file_api/config.py`
- `packages/nova_file_api/src/nova_file_api/auth.py`
- `packages/nova_file_api/src/nova_file_api/dependencies.py` if handler/runtime init changes require it
- `packages/nova_file_api/src/nova_file_api/routes/platform.py`
- new `packages/nova_file_api/src/nova_file_api/lambda_handler.py`
- `apps/nova_file_api_service/Dockerfile` (delete, replace, or demote to non-production use)
- matching infra files from Prompt 01 if the Lambda packaging/integration changes
- new and updated API tests:
  - `packages/nova_file_api/tests/test_lambda_handler_contract.py`
  - `packages/nova_file_api/tests/test_cors_contract.py`
  - `packages/nova_file_api/tests/test_authenticated_canary_flow.py`
  - `packages/nova_file_api/tests/test_runtime_security_reliability_gates.py`
  - `packages/nova_file_api/tests/test_openapi_contract.py`

## Prompt 03 — Runtime deployment control plane and provenance
Directly owns:
- new workflows:
  - `.github/workflows/deploy-runtime.yml`
  - `.github/workflows/reusable-deploy-runtime.yml`
  - optional promotion wrappers if needed
- existing workflows:
  - `.github/workflows/post-deploy-validate.yml`
  - `.github/workflows/reusable-post-deploy-validate.yml`
  - `.github/actions/configure-aws-oidc/action.yml`
- new or updated scripts:
  - `scripts/release/resolve_deploy_output.py`
  - `scripts/release/validate_runtime_release.py`
  - `scripts/release/generate_runtime_deploy_contract.py`
- new contract schemas under `docs/contracts/`
- release / client docs tied to deploy-output authority
- matching infra workflow tests under `tests/infra/`

## Prompt 04 — Security, observability, capacity, IAM hardening
Directly owns:
- infra modules introduced in Prompt 01
- alarm and logging infrastructure
- IAM scoping helpers
- S3 lifecycle configuration
- reserved concurrency settings
- WAF rate rules and logging
- Step Functions retry policies
- infra tests covering these controls
- operator runbook sections for these controls

## Prompt 05 — Validation truth, tests, docs authority, hard-cut cleanup
Directly owns:
- `scripts/release/runtime_config_contract.py`
- `docs/release/runtime-config-contract.generated.md` or its replacement
- docs routers / authority maps:
  - `README.md`
  - `AGENTS.md`
  - `docs/README.md`
  - `docs/overview/ACTIVE-DOCS-INDEX.md`
  - `docs/architecture/README.md`
  - `docs/contracts/README.md`
  - `docs/runbooks/README.md`
  - `docs/clients/README.md`
  - `docs/release/README.md`
- active ADR/spec/runbook files that remain false after the implementation
- `tests/infra/test_docs_authority_contracts.py`
- `tests/infra/test_release_workflow_contracts.py`
- `tests/infra/test_workflow_contract_docs.py`
- `scripts/checks/run_infra_contracts.sh`
- post-deploy validation and canary tests

## Prompt 99 — Final critical review and finish
May touch anything left inconsistent, but should primarily:
- verify all issue IDs are closed,
- fix any remaining drift,
- run the full validation matrix,
- produce a final change report.


<!-- FILE: prompts/01-public-ingress-hard-cut.md -->

# Prompt 01 — Hard-cut the public ingress to Regional REST API + direct WAF + one canonical custom domain

You are working inside the Nova repository. This is a **hard-cut architecture session**, not an incremental patch session.

## Common execution requirements for every Codex session

### Model and session shape
- Run this in a **fresh Codex session using `gpt-5.4-high`**.
- If your Codex environment supports concurrent helpers, spawn **2-4 focused `gpt-5.4-mini` subagents** for bounded research or file-impact exploration, then reconcile their findings before patching.
- Work on a **clean branch or stacked branch** rooted in the latest completed remediation branch. Do not mix unrelated prompts in one session.

### Mandatory tool and skill choreography
Use these in this order **when available**:

1. **`$aws-architecture` skill**
   Use it at the beginning to sanity-check the target AWS design against current AWS service guidance. Do not let it pull you back toward incremental legacy compatibility if the hard-cut target in this prompt is better.
2. **`$reducing-entropy` skill**
   Use it before design decisions and before the final patch pass. The goal is to delete dead paths, remove toggles, and simplify ownership and authority boundaries.
3. **AWS MCP tooling**
   Prefer the **AWS MCP Server** if configured and authenticated. If that is unavailable, use the **AWS Documentation MCP Server** or **AWS Knowledge MCP Server**. Use it for current AWS docs, CDK/API guidance, and read-only environment inspection when the prompt explicitly calls for it.
4. **Context7**
   Use Context7 for current version-specific docs and code examples for FastAPI, Pydantic, Mangum, uv, pytest, GitHub Actions, and AWS CDK constructs where supported.
5. **`web.run` / browser search**
   Use this whenever MCP coverage is incomplete, when the topic is recency-sensitive, or when you need the latest release notes, migration guides, or product docs. Favor official docs first.
6. **Exa search**
   Use Exa after official docs to find strong upstream implementation examples, reference repositories, or architecture examples. Do not let third-party examples override official product constraints.
7. **`$opensrc-inspect` skill**
   Use it before introducing or retaining upstream dependencies that materially affect runtime or deployment shape (for example Mangum, Lambda Web Adapter, Powertools, or new GitHub Actions helpers). Evaluate maintenance, release freshness, security posture, and issue profile.
8. **`$clean-code` skill**
   Use it before finalizing. The repo should end each session with clearer code, smaller cohesive modules, better naming, and fewer compatibility branches than it started with.

### Fallback rule
If any named tool or skill is unavailable in the Codex environment:
- state that explicitly in your session notes,
- fall back to **official docs via `web.run`** and repo-local inspection,
- continue without asking for permission.

### Code-quality and repo rules
- Use **uv only** for dependency changes, environment sync, and command execution.
- Keep runtime syntax compatible with **Python 3.11+**.
- Use **Ruff** as the formatter/linter and **mypy** as the type gate.
- Keep tests deterministic and isolated; use pytest and existing repo patterns.
- Follow the repo’s **Google-style docstring** convention where public Python APIs or non-trivial scripts are added or changed.
- Prefer deletion and simplification over compatibility toggles or dual-path support.
- Update **docs, contracts, tests, and generated artifacts together** with code changes.
- Never accept “tests pass” as proof that the target state is correct. Re-read the issue checklist at the end.

### Required end-of-session response from Codex
At the end of the session, Codex must provide:
1. a concise summary of what changed,
2. a list of changed files grouped by intent,
3. the issue IDs directly closed,
4. research sources actually consulted,
5. exact verification commands run and their outcomes,
6. residual risk or follow-up items, if any.


## Session-specific objective

Replace the current API ingress architecture with the final target state:
- **Regional API Gateway REST API**
- **direct Regional AWS WAF association**
- **one canonical custom domain**
- **default execute-api endpoint disabled**
- **no CloudFront in the API path**
- **no us-east-1-only runtime requirement**
- preserve the current public route surface as closely as possible while removing legacy/bypass paths

## Full issue register for context

# Issue register used across all prompts

Use these stable issue IDs in every Codex session. Treat them as the required acceptance contract for the remediation program.

## [P0] Merge blockers

- **P0-1 — Runtime deployment ownership deleted without replacement.** The repo still owns IaC, contracts, validation, and release docs, but no longer owns runtime deployment. There is no repo-controlled deploy/promotion chain for the live runtime.
- **P0-2 — Current CloudFront API edge cannot serve write traffic.** The surviving CloudFront distribution does not explicitly enable write methods, while the API exposes POST-heavy flows.
- **P0-3 — CloudFront/WAF is bypassable.** The API default execute-api endpoint remains reachable directly, so the supposed protected front door is not authoritative.

## [P1] High-severity design and operational defects

- **P1-1 — Browser/downstream integration has no coherent CORS model.** Browser fetch usage exists, but API Gateway and FastAPI do not form a single explicit CORS contract.
- **P1-2 — Wrong AWS ingress product mix.** The current architecture uses HTTP API plus CloudFront/WAF as a compensation layer instead of the simpler and better-fitting Regional REST API plus direct WAF attachment.
- **P1-3 — Abuse prevention is below production state.** No meaningful WAF rate limiting, stage/route throttling, or bounded public-ingress control plane exists.
- **P1-4 — Observability and forensics are below production state.** No authoritative API access logs, no WAF logs, weak alarm actions, and no single canonical public runtime authority.
- **P1-5 — Docs/specs/runbooks/contracts are internally contradictory.** Active authority still mixes old ECS/Fargate/topology/deploy assumptions with the new serverless branch shape.

## [P2] Important but non-blocking defects

- **P2-1 — Post-deploy validation is too weak.** It proves path reachability, not deployed version, correct environment, auth behavior, CORS, or provenance.
- **P2-2 — Workflow Lambdas are over-privileged.** All task functions receive broad bucket/table permissions instead of task-scoped IAM.
- **P2-3 — Runtime safeguards are missing.** Reserved concurrency, S3 lifecycle cleanup, and bounded operational defaults are missing or under-specified.
- **P2-4 — Tests validate deletions and thin invariants, not production truth.** The suite misses ingress, logging, throttling, IAM, lifecycle, and provenance defects.
- **P2-5 — Runtime path is overcomplicated.** The stack layers API Gateway auth, app auth, Lambda Web Adapter, uvicorn-in-Lambda, and deprecated compatibility shims.

## [P3] Cleanup debt that should be closed during the hard cut

- **P3-1 — Hard-cut cleanup is incomplete.** Deprecated aliases, dead contract generators, and stale docs keep deleted runtime modes and compatibility surfaces alive.

## There are no meaningful [P4] findings in the current review.


## Issue IDs this session must directly close

- **P0-2**
- **P0-3**
- **P1-2**

## Issue IDs this session must not regress and should partially prepare

- **P1-1** — establish the ingress shape needed for a real CORS contract in Prompt 02.
- **P1-3** — leave clear places for WAF rate rules and throttling that Prompt 04 can complete.
- **P1-4** — leave clear places for access logging and alarm wiring that Prompt 04 can complete.
- **P1-5** — update the minimum set of active docs needed so the repo is not immediately false after this change.
- **P2-4** — replace thin infra tests with synth assertions that reflect the new ingress truth.

## Non-negotiable end state for this session

1. The API ingress must no longer depend on CloudFront as a compensating control layer.
2. The API must no longer be modeled as API Gateway **HTTP API** for the public runtime.
3. The API must be reachable through **exactly one intended public base URL** derived from a custom domain.
4. The **default execute-api endpoint must be disabled** so the custom domain is authoritative.
5. Regional WAF must attach **directly** to the API stage in the same region.
6. The stack must no longer hard-fail outside `us-east-1`.
7. Do **not** add compatibility toggles to preserve the old CloudFront/HTTP API path.

## Repo files to read before making changes

Read these first, then expand as needed:
- `infra/nova_cdk/app.py`
- `infra/nova_cdk/README.md`
- `infra/nova_cdk/src/nova_cdk/serverless_stack.py`
- `tests/infra/test_serverless_stack_contracts.py`
- `tests/infra/helpers.py`
- `docs/architecture/README.md`
- `docs/overview/ACTIVE-DOCS-INDEX.md`
- `docs/runbooks/README.md`
- `docs/runbooks/RUNBOOK-SERVERLESS-OPERATIONS.md`
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `docs/architecture/spec/SPEC-0029-platform-serverless.md`
- `docs/architecture/spec/SPEC-0015-nova-api-platform-final-topology-and-delivery-contract.md`
- `PR-96.diff` (for deleted deployment and ingress history)

## Mandatory research before coding

Use tools in this order:

1. **`$aws-architecture`**
   - Ask it to compare:
     - Regional REST API + direct WAF + custom domain
     - Regional HTTP API + CloudFront/WAF
     - current HTTP API + CloudFront/WAF
   - Capture the architectural recommendation and constraints.

2. **AWS MCP Server / AWS Documentation MCP**
   - Verify current AWS guidance for:
     - REST vs HTTP APIs
     - direct WAF support for REST APIs
     - Regional custom domain requirements
     - disabling default REST API endpoints
     - API mappings / base path mapping
     - REST API logging hooks
   - If authenticated AWS environment access exists, do **read-only** inspection only. Do not mutate live resources in this session.

3. **Context7**
   - Fetch current docs/examples for:
     - AWS CDK v2 Python `aws_apigateway`
     - `aws_wafv2`
     - custom domain / Route53 / ACM constructs
     - any CDK property needed to disable the default REST endpoint

4. **Exa**
   - Find strong upstream examples for:
     - REST API + Lambda proxy + custom domain in CDK
     - WAF association to API Gateway REST API stages
   - Treat these as examples only after official docs define the constraints.

5. **`web.run` fallback**
   - Use it for any gap or conflicting information.

## Recommended `gpt-5.4-mini` subagents

If supported, delegate:
- **mini-1:** current AWS product and CDK research with links and concrete property names.
- **mini-2:** repo-local file impact analysis: every file that mentions CloudFront, HTTP API, execute-api, WAF, or `us-east-1`.
- **mini-3:** infra test rewrite plan and doc/router files that become false once the ingress changes.

## Files that must be changed in this session

### Existing files that must be edited or deleted
- `infra/nova_cdk/app.py`
- `infra/nova_cdk/README.md`
- `infra/nova_cdk/src/nova_cdk/__init__.py`
- `infra/nova_cdk/src/nova_cdk/serverless_stack.py`
  Delete it or reduce it to a compatibility-free import shim only if strictly necessary to land a coherent modular stack.
- `tests/infra/test_serverless_stack_contracts.py`
  Replace or split it so it tests the new ingress truth rather than the old HTTP API shape.
- `docs/architecture/README.md`
- `docs/runbooks/README.md`
- `docs/runbooks/RUNBOOK-SERVERLESS-OPERATIONS.md`
  Update or supersede the minimum ingress statements that would otherwise remain false.

### New files strongly expected
- `infra/nova_cdk/src/nova_cdk/runtime_stack.py`
- `infra/nova_cdk/src/nova_cdk/ingress.py` or equivalent
- `infra/nova_cdk/src/nova_cdk/data_plane.py` if splitting is cleaner
- `tests/infra/test_runtime_stack_contracts.py`
- `tests/infra/test_ingress_contracts.py`

### Files that may need updates if they mention the old ingress
- `docs/overview/ACTIVE-DOCS-INDEX.md`
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `docs/architecture/spec/SPEC-0029-platform-serverless.md`

## Implementation requirements

### 1. Replace the ingress product
- Remove `aws_apigatewayv2.HttpApi` from the public runtime path.
- Use Regional **REST API** constructs instead.
- Preserve the canonical route namespace and route shapes.

### 2. Delete the CloudFront API front door
- Remove the API-facing CloudFront distribution and its API origin wiring.
- Remove CloudFront-scoped WAF for the API path.
- Remove the `us-east-1` restriction caused by CloudFront-scoped WAF.

### 3. Make the custom domain authoritative
- Introduce a Regional custom domain for the API.
- Disable the default `execute-api` endpoint.
- Expose one authoritative output such as `NovaPublicBaseUrl`.
- Remove or supersede exports that encouraged direct use of the old execute-api or CloudFront hostnames.

### 4. Associate WAF directly with the API stage
- Use a **Regional** web ACL in the same region as the API.
- Ensure the resource ARN points to the REST API stage.
- Do not leave a CloudFront WAF association behind for the API path.

### 5. Design for later hardening, not later rework
- Leave explicit, clean insertion points for:
  - WAF rate-based rules,
  - API access logging,
  - alarm wiring,
  - throttling,
  - custom-domain-driven endpoint publication.
- Do not bake these in as TODO comments only; shape the stack so Prompt 04 can add them without re-architecting.

### 6. Test the new truth
Add or update synth assertions so the suite checks:
- REST API exists instead of HTTP API.
- CloudFront distribution for the API path is gone.
- default execute-api endpoint is disabled.
- one canonical public base URL output exists.
- WAF association targets the REST API stage.
- `us-east-1` is no longer hard-required.
- route surface still contains the required health, metrics, and `/v1` paths.

### 7. Keep changes clean
- Prefer a modular stack split if that reduces complexity.
- Do not preserve `serverless_stack.py` as a large compatibility dump.
- Do not preserve old outputs just because downstream code might have depended on them. This is a hard cut.

## Linked issue-closure checklist

Mark these as done in your own session notes before finishing:
- [ ] **P0-2:** no CloudFront default-behavior method trap remains in the API path because CloudFront is removed from the API path entirely.
- [ ] **P0-3:** default `execute-api` endpoint is disabled and no public bypass path remains.
- [ ] **P1-2:** the public ingress is Regional REST API + direct Regional WAF, not HTTP API + CloudFront/WAF.
- [ ] **P2-4 (partial):** infra tests assert the new ingress truth.
- [ ] Active docs no longer claim the API is served through the old ingress shape.

## Success criteria

This session is only complete if all of the following are true:
- `infra/nova_cdk/app.py` synthesizes outside `us-east-1`.
- There is no API CloudFront distribution left in the main runtime stack.
- The runtime stack outputs a canonical custom-domain-based base URL.
- The default execute-api endpoint is disabled.
- The synth tests would fail if someone reintroduced HTTP API or CloudFront for the API path.
- Docs directly adjacent to the ingress no longer lie.

## Verification commands

Run all of these unless a command becomes obsolete because you renamed a test file. If a command name changes, run the equivalent and state the replacement explicitly.

```bash
uv sync --locked --all-extras --dev
uv run ruff check --fix
uv run ruff format
uv run ruff check
uv run mypy .
uv run pytest tests/infra -q
uv run --package nova-cdk cdk synth   -c account=111111111111   -c region=us-west-2   -c environment=dev   -c jwt_issuer=https://issuer.example.com/   -c jwt_audience=api://nova   -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json   -c api_domain_name=api.dev.example.com   -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000
```

## References to use in this session

## Core current references that should be consulted where relevant

### AWS / GitHub / Python platform docs
- AWS API Gateway: REST vs HTTP APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html
- AWS API Gateway: protect REST APIs with AWS WAF
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html
- AWS API Gateway: disable default endpoint for REST APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-disable-default-endpoint.html
- AWS API Gateway: Regional custom domain names
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-regional-api-custom-domain-create.html
- AWS API Gateway: API mappings for custom domains
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-mappings.html
- AWS API Gateway: integration types
  https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-integration-types.html
- AWS CDK CloudFront behavior defaults
  https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudfront/Behavior.html
- AWS WAF rate-based rules
  https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html
- AWS WAF logging
  https://docs.aws.amazon.com/waf/latest/developerguide/logging.html
- API Gateway logging
  https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html
- Lambda reserved concurrency
  https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html
- Lambda concurrency concepts
  https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html
- S3 abort incomplete multipart uploads
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html
- Step Functions retries and error handling
  https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html
- GitHub Actions OIDC in AWS
  https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- GitHub Actions reusable workflows
  https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows
- GitHub Actions artifact attestations
  https://docs.github.com/en/actions/concepts/security/artifact-attestations
- OpenAI Codex MCP
  https://developers.openai.com/codex/mcp
- OpenAI Codex skills
  https://developers.openai.com/codex/skills/
- OpenAI Docs MCP
  https://developers.openai.com/learn/docs-mcp/
- uv locking and syncing
  https://docs.astral.sh/uv/concepts/projects/sync/
- uv workspaces
  https://docs.astral.sh/uv/concepts/projects/workspaces/
- pytest good practices / importlib mode
  https://docs.pytest.org/en/stable/explanation/goodpractices.html
- FastAPI CORS
  https://fastapi.tiangolo.com/tutorial/cors/
- FastAPI settings / Pydantic settings
  https://fastapi.tiangolo.com/advanced/settings/
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Google Python Style Guide
  https://google.github.io/styleguide/pyguide.html

### AWS / documentation MCP references
- AWS MCP Server user guide
  https://docs.aws.amazon.com/aws-mcp/latest/userguide/what-is-mcp-server.html
- AWS Documentation MCP Server
  https://awslabs.github.io/mcp/servers/aws-documentation-mcp-server
- AWS Knowledge MCP Server
  https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server

### Context7 / Exa
- Context7 GitHub / setup docs
  https://github.com/upstash/context7
- Exa search docs
  https://exa.ai/docs/reference/search-api-guide
  https://exa.ai/docs/reference/search-best-practices

### Upstream runtime examples to inspect only after official docs
- Mangum upstream
  https://github.com/Kludex/mangum
  https://mangum.fastapiexpert.com/
- AWS Lambda Web Adapter upstream
  https://github.com/awslabs/aws-lambda-web-adapter



<!-- FILE: prompts/02-runtime-simplification-cors-auth.md -->

# Prompt 02 — Simplify the FastAPI runtime to native Lambda proxy handling, unify CORS, and remove dead compatibility/auth layering

You are working inside the Nova repository. This is a **runtime simplification and browser-contract session**. Prefer deletion and a cleaner final state over incremental dual support.

## Common execution requirements for every Codex session

### Model and session shape
- Run this in a **fresh Codex session using `gpt-5.4-high`**.
- If your Codex environment supports concurrent helpers, spawn **2-4 focused `gpt-5.4-mini` subagents** for bounded research or file-impact exploration, then reconcile their findings before patching.
- Work on a **clean branch or stacked branch** rooted in the latest completed remediation branch. Do not mix unrelated prompts in one session.

### Mandatory tool and skill choreography
Use these in this order **when available**:

1. **`$aws-architecture` skill**
   Use it at the beginning to sanity-check the target AWS design against current AWS service guidance. Do not let it pull you back toward incremental legacy compatibility if the hard-cut target in this prompt is better.
2. **`$reducing-entropy` skill**
   Use it before design decisions and before the final patch pass. The goal is to delete dead paths, remove toggles, and simplify ownership and authority boundaries.
3. **AWS MCP tooling**
   Prefer the **AWS MCP Server** if configured and authenticated. If that is unavailable, use the **AWS Documentation MCP Server** or **AWS Knowledge MCP Server**. Use it for current AWS docs, CDK/API guidance, and read-only environment inspection when the prompt explicitly calls for it.
4. **Context7**
   Use Context7 for current version-specific docs and code examples for FastAPI, Pydantic, Mangum, uv, pytest, GitHub Actions, and AWS CDK constructs where supported.
5. **`web.run` / browser search**
   Use this whenever MCP coverage is incomplete, when the topic is recency-sensitive, or when you need the latest release notes, migration guides, or product docs. Favor official docs first.
6. **Exa search**
   Use Exa after official docs to find strong upstream implementation examples, reference repositories, or architecture examples. Do not let third-party examples override official product constraints.
7. **`$opensrc-inspect` skill**
   Use it before introducing or retaining upstream dependencies that materially affect runtime or deployment shape (for example Mangum, Lambda Web Adapter, Powertools, or new GitHub Actions helpers). Evaluate maintenance, release freshness, security posture, and issue profile.
8. **`$clean-code` skill**
   Use it before finalizing. The repo should end each session with clearer code, smaller cohesive modules, better naming, and fewer compatibility branches than it started with.

### Fallback rule
If any named tool or skill is unavailable in the Codex environment:
- state that explicitly in your session notes,
- fall back to **official docs via `web.run`** and repo-local inspection,
- continue without asking for permission.

### Code-quality and repo rules
- Use **uv only** for dependency changes, environment sync, and command execution.
- Keep runtime syntax compatible with **Python 3.11+**.
- Use **Ruff** as the formatter/linter and **mypy** as the type gate.
- Keep tests deterministic and isolated; use pytest and existing repo patterns.
- Follow the repo’s **Google-style docstring** convention where public Python APIs or non-trivial scripts are added or changed.
- Prefer deletion and simplification over compatibility toggles or dual-path support.
- Update **docs, contracts, tests, and generated artifacts together** with code changes.
- Never accept “tests pass” as proof that the target state is correct. Re-read the issue checklist at the end.

### Required end-of-session response from Codex
At the end of the session, Codex must provide:
1. a concise summary of what changed,
2. a list of changed files grouped by intent,
3. the issue IDs directly closed,
4. research sources actually consulted,
5. exact verification commands run and their outcomes,
6. residual risk or follow-up items, if any.


## Session-specific objective

Land the final runtime shape for the FastAPI service:
- **native Lambda proxy handling** for the FastAPI app (Mangum or equivalent),
- **no production uvicorn process inside Lambda**,
- **no Lambda Web Adapter in the production path**,
- **one coherent CORS model** across app/dev and infra contracts,
- **app-level auth as the canonical source of truth** unless a stronger reason emerges from current docs and repo behavior,
- remove deprecated compatibility aliases and dead runtime-contract surfaces that survived the hard cut.

## Full issue register for context

# Issue register used across all prompts

Use these stable issue IDs in every Codex session. Treat them as the required acceptance contract for the remediation program.

## [P0] Merge blockers

- **P0-1 — Runtime deployment ownership deleted without replacement.** The repo still owns IaC, contracts, validation, and release docs, but no longer owns runtime deployment. There is no repo-controlled deploy/promotion chain for the live runtime.
- **P0-2 — Current CloudFront API edge cannot serve write traffic.** The surviving CloudFront distribution does not explicitly enable write methods, while the API exposes POST-heavy flows.
- **P0-3 — CloudFront/WAF is bypassable.** The API default execute-api endpoint remains reachable directly, so the supposed protected front door is not authoritative.

## [P1] High-severity design and operational defects

- **P1-1 — Browser/downstream integration has no coherent CORS model.** Browser fetch usage exists, but API Gateway and FastAPI do not form a single explicit CORS contract.
- **P1-2 — Wrong AWS ingress product mix.** The current architecture uses HTTP API plus CloudFront/WAF as a compensation layer instead of the simpler and better-fitting Regional REST API plus direct WAF attachment.
- **P1-3 — Abuse prevention is below production state.** No meaningful WAF rate limiting, stage/route throttling, or bounded public-ingress control plane exists.
- **P1-4 — Observability and forensics are below production state.** No authoritative API access logs, no WAF logs, weak alarm actions, and no single canonical public runtime authority.
- **P1-5 — Docs/specs/runbooks/contracts are internally contradictory.** Active authority still mixes old ECS/Fargate/topology/deploy assumptions with the new serverless branch shape.

## [P2] Important but non-blocking defects

- **P2-1 — Post-deploy validation is too weak.** It proves path reachability, not deployed version, correct environment, auth behavior, CORS, or provenance.
- **P2-2 — Workflow Lambdas are over-privileged.** All task functions receive broad bucket/table permissions instead of task-scoped IAM.
- **P2-3 — Runtime safeguards are missing.** Reserved concurrency, S3 lifecycle cleanup, and bounded operational defaults are missing or under-specified.
- **P2-4 — Tests validate deletions and thin invariants, not production truth.** The suite misses ingress, logging, throttling, IAM, lifecycle, and provenance defects.
- **P2-5 — Runtime path is overcomplicated.** The stack layers API Gateway auth, app auth, Lambda Web Adapter, uvicorn-in-Lambda, and deprecated compatibility shims.

## [P3] Cleanup debt that should be closed during the hard cut

- **P3-1 — Hard-cut cleanup is incomplete.** Deprecated aliases, dead contract generators, and stale docs keep deleted runtime modes and compatibility surfaces alive.

## There are no meaningful [P4] findings in the current review.


## Issue IDs this session must directly close

- **P1-1**
- **P2-5**
- **P3-1**

## Issue IDs this session must not regress and should support

- **P0-2 / P0-3 / P1-2** — preserve the ingress hard cut from Prompt 01.
- **P1-3 / P1-4** — expose clean hooks for throttling/logging/observability, not more runtime indirection.
- **P2-1** — ensure `/v1/releases/info` and the runtime can later support provenance-aware validation cleanly.
- **P2-4** — add tests that assert the new handler path and CORS contract.

## Non-negotiable end state for this session

1. The production Lambda path must no longer run `uvicorn` inside the function.
2. The production Lambda path must no longer depend on AWS Lambda Web Adapter.
3. FastAPI remains the API contract/OpenAPI engine.
4. The API runtime must expose a clean native Lambda handler.
5. Allowed origins must become a single intentional contract, not an accidental mix of S3-only CORS plus browser fetch usage.
6. Deprecated settings aliases and dead compatibility surfaces should be removed unless there is a documented user-facing compatibility requirement.

## Repo files to read before making changes

Read these first:
- `packages/nova_file_api/pyproject.toml`
- `packages/nova_file_api/src/nova_file_api/app.py`
- `packages/nova_file_api/src/nova_file_api/main.py`
- `packages/nova_file_api/src/nova_file_api/config.py`
- `packages/nova_file_api/src/nova_file_api/auth.py`
- `packages/nova_file_api/src/nova_file_api/dependencies.py`
- `packages/nova_file_api/src/nova_file_api/routes/platform.py`
- `packages/nova_file_api/tests/test_runtime_security_reliability_gates.py`
- `packages/nova_file_api/tests/test_openapi_contract.py`
- `packages/nova_file_api/tests/test_auth.py`
- `packages/nova_file_api/tests/test_v1_api.py`
- `apps/nova_file_api_service/Dockerfile`
- `packages/nova_dash_bridge/src/nova_dash_bridge/assets/file_transfer.js`
- the runtime stack files created in Prompt 01

## Mandatory research before coding

1. **`$reducing-entropy`**
   - Use it up front on the current runtime path and ask what can be deleted immediately once native Lambda proxy handling exists.

2. **`$opensrc-inspect`**
   - Evaluate:
     - `mangum`
     - `awslabs/aws-lambda-web-adapter`
     - optionally `aws-lambda-powertools`
   - You are not required to add Powertools, but inspect it if you are tempted to introduce it.

3. **Context7**
   - Fetch current docs/examples for:
     - FastAPI CORS
     - FastAPI settings
     - Pydantic settings
     - Mangum (if available through Context7)
     - pytest patterns for handler/integration testing

4. **AWS MCP / AWS docs**
   - Reconfirm API Gateway Lambda proxy integration guidance and any integration requirements that matter for response headers and CORS behavior.

5. **Exa**
   - Find strong upstream examples for:
     - FastAPI + Mangum + API Gateway
     - native Lambda handler layouts that preserve OpenAPI and local dev

6. **`web.run` fallback**
   - Use official docs first; use upstream repo docs next.

## Recommended `gpt-5.4-mini` subagents

- **mini-1:** compare Mangum vs Lambda Web Adapter for this repo’s use case and report the simplest final-state recommendation.
- **mini-2:** trace every code path that assumes `uvicorn` or Docker-image-only invocation.
- **mini-3:** map browser/CORS interactions across FastAPI app, API Gateway, S3, tests, and client examples.

## Files that must be changed in this session

### Existing files that must be edited or deleted
- `packages/nova_file_api/pyproject.toml`
- `packages/nova_file_api/src/nova_file_api/app.py`
- `packages/nova_file_api/src/nova_file_api/main.py`
- `packages/nova_file_api/src/nova_file_api/config.py`
- `packages/nova_file_api/src/nova_file_api/auth.py`
- `packages/nova_file_api/src/nova_file_api/dependencies.py` if runtime init changes need it
- `packages/nova_file_api/src/nova_file_api/routes/platform.py`
- `apps/nova_file_api_service/Dockerfile`
  Delete it, replace it, or explicitly demote it to non-production-only use. Do not leave it as the active production Lambda path.
- the Lambda function definition in the infra stack from Prompt 01 so it invokes the new native handler path
- `packages/nova_file_api/tests/test_runtime_security_reliability_gates.py`
- `packages/nova_file_api/tests/test_auth.py`
- `packages/nova_file_api/tests/test_openapi_contract.py`

### New files strongly expected
- `packages/nova_file_api/src/nova_file_api/lambda_handler.py`
- `packages/nova_file_api/tests/test_lambda_handler_contract.py`
- `packages/nova_file_api/tests/test_cors_contract.py`
- `packages/nova_file_api/tests/test_authenticated_canary_flow.py` or equivalent golden-flow tests

### Files that may need updates
- `infra/nova_cdk/src/nova_cdk/runtime_stack.py` or equivalent from Prompt 01
- `packages/nova_file_api/README.md`
- any generated-contract or runtime-config files that still mention the old handler path

## Implementation requirements

### 1. Introduce a native Lambda handler
- Add a stable native Lambda entrypoint for the FastAPI app.
- Prefer **Mangum** if the upstream inspection and current ecosystem state support it cleanly.
- Lazy-load or cache the app where appropriate for Lambda reuse.
- Preserve local dev ergonomics: `uvicorn` can remain a local dev tool, but it must no longer be the production Lambda invocation model.

### 2. Remove AWS Lambda Web Adapter from the production path
- Remove the active production dependency on `/opt/extensions/lambda-adapter`.
- Remove the production `CMD ["uvicorn", ...]` pattern.
- Do not leave commented or “just in case” production fallback logic.

### 3. Unify the CORS contract
- Add an intentional allowed-origins configuration shape.
- Ensure local/dev FastAPI runs include explicit CORS handling where browser development needs it.
- Coordinate the runtime config with the ingress/IaC shape introduced in Prompt 01.
- Make sure the contract covers:
  - preflight behavior,
  - allowed headers,
  - allowed methods,
  - credentials policy,
  - S3 upload-side needs where relevant.

### 4. Simplify auth layering
- Keep app-level JWT verification as the canonical truth unless current research and actual route behavior prove a strong need for duplicate gateway auth.
- Remove or stop depending on duplicate auth layers if they now exist after Prompt 01.
- Preserve public health semantics and protected-route behavior.

### 5. Remove dead compatibility surfaces
- Delete deprecated settings aliases and stale runtime-mode shims unless a real consumer compatibility requirement is documented.
- Do not preserve deleted worker/service template contract assumptions in config or generated docs.

### 6. Update tests to prove the new runtime truth
Add or update tests so the suite checks:
- a native Lambda event can invoke the app successfully,
- the old Web Adapter / uvicorn production path is gone,
- CORS preflight and actual browser-relevant headers are correct,
- `/v1/releases/info` still behaves correctly,
- OpenAPI generation still works,
- the handler path and local-dev path both remain maintainable.

## Linked issue-closure checklist

- [x] **P1-1:** a coherent CORS model exists and is tested.
- [x] **P2-5:** production runtime no longer depends on uvicorn-in-Lambda or Lambda Web Adapter.
- [x] **P3-1:** deprecated aliases and dead compatibility/runtime surfaces are removed or clearly retired.
- [x] Protected-route behavior still works and health routes remain public.
- [x] OpenAPI and SDK-generation prerequisites remain intact.

## Success criteria

This session is only complete if all of the following are true:
- there is a native Lambda handler under `packages/nova_file_api/src/nova_file_api/`,
- the active production path no longer uses Lambda Web Adapter,
- the active production path no longer runs uvicorn inside Lambda,
- CORS behavior is explicit and tested,
- OpenAPI still exports cleanly,
- the runtime configuration surface is smaller and clearer than before this session.

## Verification commands

```bash
uv sync --locked --all-extras --dev
uv run ruff check --fix
uv run ruff format
uv run ruff check
uv run mypy .
uv run pytest packages/nova_file_api/tests -q
uv run python scripts/contracts/export_openapi.py --check
uv run python scripts/release/generate_clients.py --check
uv run python scripts/release/generate_python_clients.py --check
uv run pytest tests/infra -q
```

## References to use in this session

## Core current references that should be consulted where relevant

### AWS / GitHub / Python platform docs
- AWS API Gateway: REST vs HTTP APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html
- AWS API Gateway: protect REST APIs with AWS WAF
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html
- AWS API Gateway: disable default endpoint for REST APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-disable-default-endpoint.html
- AWS API Gateway: Regional custom domain names
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-regional-api-custom-domain-create.html
- AWS API Gateway: API mappings for custom domains
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-mappings.html
- AWS API Gateway: integration types
  https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-integration-types.html
- AWS CDK CloudFront behavior defaults
  https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudfront/Behavior.html
- AWS WAF rate-based rules
  https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html
- AWS WAF logging
  https://docs.aws.amazon.com/waf/latest/developerguide/logging.html
- API Gateway logging
  https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html
- Lambda reserved concurrency
  https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html
- Lambda concurrency concepts
  https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html
- S3 abort incomplete multipart uploads
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html
- Step Functions retries and error handling
  https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html
- GitHub Actions OIDC in AWS
  https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- GitHub Actions reusable workflows
  https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows
- GitHub Actions artifact attestations
  https://docs.github.com/en/actions/concepts/security/artifact-attestations
- OpenAI Codex MCP
  https://developers.openai.com/codex/mcp
- OpenAI Codex skills
  https://developers.openai.com/codex/skills/
- OpenAI Docs MCP
  https://developers.openai.com/learn/docs-mcp/
- uv locking and syncing
  https://docs.astral.sh/uv/concepts/projects/sync/
- uv workspaces
  https://docs.astral.sh/uv/concepts/projects/workspaces/
- pytest good practices / importlib mode
  https://docs.pytest.org/en/stable/explanation/goodpractices.html
- FastAPI CORS
  https://fastapi.tiangolo.com/tutorial/cors/
- FastAPI settings / Pydantic settings
  https://fastapi.tiangolo.com/advanced/settings/
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Google Python Style Guide
  https://google.github.io/styleguide/pyguide.html

### AWS / documentation MCP references
- AWS MCP Server user guide
  https://docs.aws.amazon.com/aws-mcp/latest/userguide/what-is-mcp-server.html
- AWS Documentation MCP Server
  https://awslabs.github.io/mcp/servers/aws-documentation-mcp-server
- AWS Knowledge MCP Server
  https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server

### Context7 / Exa
- Context7 GitHub / setup docs
  https://github.com/upstash/context7
- Exa search docs
  https://exa.ai/docs/reference/search-api-guide
  https://exa.ai/docs/reference/search-best-practices

### Upstream runtime examples to inspect only after official docs
- Mangum upstream
  https://github.com/Kludex/mangum
  https://mangum.fastapiexpert.com/
- AWS Lambda Web Adapter upstream
  https://github.com/awslabs/aws-lambda-web-adapter


### Additional runtime-focused upstream references
- Mangum upstream docs and repo:
  https://mangum.fastapiexpert.com/
  https://github.com/Kludex/mangum
- AWS Lambda Web Adapter upstream:
  https://github.com/awslabs/aws-lambda-web-adapter


<!-- FILE: prompts/03-runtime-deploy-oidc-provenance.md -->

# Prompt 03 — Restore repo-owned runtime deployment via GitHub OIDC and make deploy-output provenance authoritative

> Status: Completed on 2026-03-29
>
> Directly closed issue IDs: `P0-1`, `P2-1` (provenance and deploy-output half), `P1-5` (workflow / contract / release-doc half)
>
> Completion summary:
>
> - Restored repo-owned runtime deployment with `deploy-runtime` and `reusable-deploy-runtime` as the canonical runtime deploy API.
> - Bound runtime deployment to AWS OIDC, reusable workflows, immutable `release-apply` artifacts, and authoritative deploy-output artifacts.
> - Reworked post-deploy validation to resolve deploy authority from deploy-output artifacts instead of a free-text base URL.
> - Updated workflow contracts, release/client docs, provisioning runbooks, and infra tests to the repo-owned runtime deploy story.

You are working inside the Nova repository. This is a **deployment authority and provenance session**. The goal is to restore repo ownership of the runtime delivery chain.

## Common execution requirements for every Codex session

### Model and session shape
- Run this in a **fresh Codex session using `gpt-5.4-high`**.
- If your Codex environment supports concurrent helpers, spawn **2-4 focused `gpt-5.4-mini` subagents** for bounded research or file-impact exploration, then reconcile their findings before patching.
- Work on a **clean branch or stacked branch** rooted in the latest completed remediation branch. Do not mix unrelated prompts in one session.

### Mandatory tool and skill choreography
Use these in this order **when available**:

1. **`$aws-architecture` skill**
   Use it at the beginning to sanity-check the target AWS design against current AWS service guidance. Do not let it pull you back toward incremental legacy compatibility if the hard-cut target in this prompt is better.
2. **`$reducing-entropy` skill**
   Use it before design decisions and before the final patch pass. The goal is to delete dead paths, remove toggles, and simplify ownership and authority boundaries.
3. **AWS MCP tooling**
   Prefer the **AWS MCP Server** if configured and authenticated. If that is unavailable, use the **AWS Documentation MCP Server** or **AWS Knowledge MCP Server**. Use it for current AWS docs, CDK/API guidance, and read-only environment inspection when the prompt explicitly calls for it.
4. **Context7**
   Use Context7 for current version-specific docs and code examples for FastAPI, Pydantic, Mangum, uv, pytest, GitHub Actions, and AWS CDK constructs where supported.
5. **`web.run` / browser search**
   Use this whenever MCP coverage is incomplete, when the topic is recency-sensitive, or when you need the latest release notes, migration guides, or product docs. Favor official docs first.
6. **Exa search**
   Use Exa after official docs to find strong upstream implementation examples, reference repositories, or architecture examples. Do not let third-party examples override official product constraints.
7. **`$opensrc-inspect` skill**
   Use it before introducing or retaining upstream dependencies that materially affect runtime or deployment shape (for example Mangum, Lambda Web Adapter, Powertools, or new GitHub Actions helpers). Evaluate maintenance, release freshness, security posture, and issue profile.
8. **`$clean-code` skill**
   Use it before finalizing. The repo should end each session with clearer code, smaller cohesive modules, better naming, and fewer compatibility branches than it started with.

### Fallback rule
If any named tool or skill is unavailable in the Codex environment:
- state that explicitly in your session notes,
- fall back to **official docs via `web.run`** and repo-local inspection,
- continue without asking for permission.

### Code-quality and repo rules
- Use **uv only** for dependency changes, environment sync, and command execution.
- Keep runtime syntax compatible with **Python 3.11+**.
- Use **Ruff** as the formatter/linter and **mypy** as the type gate.
- Keep tests deterministic and isolated; use pytest and existing repo patterns.
- Follow the repo’s **Google-style docstring** convention where public Python APIs or non-trivial scripts are added or changed.
- Prefer deletion and simplification over compatibility toggles or dual-path support.
- Update **docs, contracts, tests, and generated artifacts together** with code changes.
- Never accept “tests pass” as proof that the target state is correct. Re-read the issue checklist at the end.

### Required end-of-session response from Codex
At the end of the session, Codex must provide:
1. a concise summary of what changed,
2. a list of changed files grouped by intent,
3. the issue IDs directly closed,
4. research sources actually consulted,
5. exact verification commands run and their outcomes,
6. residual risk or follow-up items, if any.


## Session-specific objective

Reintroduce a repo-owned runtime deployment control plane that:
- deploys the runtime through GitHub Actions using **AWS OIDC**,
- uses **reusable workflows** as the canonical API surface,
- emits a **deploy-output authority artifact** that binds git SHA, runtime version, stack outputs, and canonical public base URL,
- updates post-deploy validation so it consumes the authoritative deploy artifact instead of a free-text URL.

## Full issue register for context

# Issue register used across all prompts

Use these stable issue IDs in every Codex session. Treat them as the required acceptance contract for the remediation program.

## [P0] Merge blockers

- **P0-1 — Runtime deployment ownership deleted without replacement.** The repo still owns IaC, contracts, validation, and release docs, but no longer owns runtime deployment. There is no repo-controlled deploy/promotion chain for the live runtime.
- **P0-2 — Current CloudFront API edge cannot serve write traffic.** The surviving CloudFront distribution does not explicitly enable write methods, while the API exposes POST-heavy flows.
- **P0-3 — CloudFront/WAF is bypassable.** The API default execute-api endpoint remains reachable directly, so the supposed protected front door is not authoritative.

## [P1] High-severity design and operational defects

- **P1-1 — Browser/downstream integration has no coherent CORS model.** Browser fetch usage exists, but API Gateway and FastAPI do not form a single explicit CORS contract.
- **P1-2 — Wrong AWS ingress product mix.** The current architecture uses HTTP API plus CloudFront/WAF as a compensation layer instead of the simpler and better-fitting Regional REST API plus direct WAF attachment.
- **P1-3 — Abuse prevention is below production state.** No meaningful WAF rate limiting, stage/route throttling, or bounded public-ingress control plane exists.
- **P1-4 — Observability and forensics are below production state.** No authoritative API access logs, no WAF logs, weak alarm actions, and no single canonical public runtime authority.
- **P1-5 — Docs/specs/runbooks/contracts are internally contradictory.** Active authority still mixes old ECS/Fargate/topology/deploy assumptions with the new serverless branch shape.

## [P2] Important but non-blocking defects

- **P2-1 — Post-deploy validation is too weak.** It proves path reachability, not deployed version, correct environment, auth behavior, CORS, or provenance.
- **P2-2 — Workflow Lambdas are over-privileged.** All task functions receive broad bucket/table permissions instead of task-scoped IAM.
- **P2-3 — Runtime safeguards are missing.** Reserved concurrency, S3 lifecycle cleanup, and bounded operational defaults are missing or under-specified.
- **P2-4 — Tests validate deletions and thin invariants, not production truth.** The suite misses ingress, logging, throttling, IAM, lifecycle, and provenance defects.
- **P2-5 — Runtime path is overcomplicated.** The stack layers API Gateway auth, app auth, Lambda Web Adapter, uvicorn-in-Lambda, and deprecated compatibility shims.

## [P3] Cleanup debt that should be closed during the hard cut

- **P3-1 — Hard-cut cleanup is incomplete.** Deprecated aliases, dead contract generators, and stale docs keep deleted runtime modes and compatibility surfaces alive.

## There are no meaningful [P4] findings in the current review.


## Issue IDs this session must directly close

- **P0-1**
- **P2-1** (provenance and deploy-output half)
- **P1-5** (workflow / contract / release-doc half)

## Issue IDs this session must not regress and should support

- **P0-2 / P0-3 / P1-2** — preserve the hard-cut ingress outputs and public-base-URL model from Prompts 01-02.
- **P1-4** — improve provenance and runtime authority in a way that supports stronger observability and incident response.
- **P2-4** — add workflow and contract tests that validate the new truth.
- **P3-1** — do not reintroduce deleted CodePipeline/CodeBuild control-plane surfaces.

## Non-negotiable end state for this session

1. The repo again owns runtime deployment through GitHub Actions.
2. Deployment uses OIDC, not long-lived AWS secrets.
3. Runtime deployment and runtime validation consume a canonical deploy-output artifact.
4. The repo has an explicit reusable workflow API for runtime deployment.
5. The old “manual or external deployment” assumption is no longer the active release story.
6. Do not resurrect the old CodePipeline/CodeBuild or deploy-runtime CloudFormation-era control plane.

## Repo files to read before making changes

Read these first:
- `.github/actions/configure-aws-oidc/action.yml`
- `.github/workflows/post-deploy-validate.yml`
- `.github/workflows/reusable-post-deploy-validate.yml`
- `.github/workflows/release-plan.yml`
- `.github/workflows/reusable-release-plan.yml`
- `.github/workflows/release-apply.yml`
- `.github/workflows/reusable-release-apply.yml`
- `.github/workflows/promote-prod.yml`
- `.github/workflows/reusable-promote-prod.yml`
- `tests/infra/test_release_workflow_contracts.py`
- `tests/infra/test_workflow_contract_docs.py`
- `docs/contracts/README.md`
- `docs/clients/post-deploy-validation-integration-guide.md`
- `docs/runbooks/release/release-runbook.md`
- `infra/nova_cdk/README.md`
- outputs or public-base-url wiring introduced in Prompts 01-02

## Mandatory research before coding

1. **AWS MCP / AWS docs**
   - Reconfirm CDK deploy expectations and any AWS-side OIDC constraints that matter to the runtime deploy role.
   - If you have AWS read-only access, inspect whether current repo assumptions about role partitioning still make sense. Do not mutate live IAM in this coding session.

2. **GitHub docs**
   - OIDC in AWS
   - reusable workflows (`workflow_call`)
   - artifact attestations / provenance

3. **Context7**
   - Fetch current GitHub Actions syntax, best-practice examples, and workflow-call patterns if available.
   - Fetch current uv usage guidance where workflow install patterns matter.

4. **Exa**
   - Find strong examples for reusable deploy workflows and OIDC-to-CDK runtime deploys.
   - Use examples only after official docs establish the rules.

5. **`$reducing-entropy`**
   - Ask what deployment/doc/contract surfaces can be deleted once runtime deploy authority returns to the repo.

## Recommended `gpt-5.4-mini` subagents

- **mini-1:** workflow API design and OIDC research.
- **mini-2:** contract schema and release-doc impact mapping.
- **mini-3:** post-deploy validation/provenance redesign plan.

## Files that must be changed in this session

### Existing files that must be edited
- `.github/actions/configure-aws-oidc/action.yml` if its interface or session tagging needs improvement
- `.github/workflows/post-deploy-validate.yml`
- `.github/workflows/reusable-post-deploy-validate.yml`
- `tests/infra/test_release_workflow_contracts.py`
- `tests/infra/test_workflow_contract_docs.py`
- `docs/contracts/README.md`
- `docs/clients/post-deploy-validation-integration-guide.md`
- `docs/runbooks/release/release-runbook.md`
- `infra/nova_cdk/README.md`

### New files strongly expected
- `.github/workflows/deploy-runtime.yml`
- `.github/workflows/reusable-deploy-runtime.yml`
- optional environment or promotion wrappers if your workflow design needs them
- `scripts/release/resolve_deploy_output.py`
- `scripts/release/validate_runtime_release.py` or equivalent provenance-aware validator entrypoint
- `scripts/release/generate_runtime_deploy_contract.py`
- `docs/contracts/deploy-output-authority-v2.schema.json`
- `docs/contracts/workflow-deploy-runtime-v1.schema.json`
- possibly `docs/contracts/workflow-promote-runtime-v1.schema.json` if you split deploy and promote
- tests such as:
  - `tests/infra/test_runtime_deploy_workflow_contracts.py`
  - `tests/infra/test_deploy_output_contracts.py`

### Files that may need coordinated updates
- workflow schemas or release-artifact schemas under `docs/contracts/`
- client examples under `docs/clients/examples/workflows/`
- stack outputs or scripts that expose runtime version/public base URL

## Implementation requirements

### 1. Reintroduce repo-owned runtime deployment
- Add a reusable runtime deploy workflow API using `workflow_call`.
- Add at least one wrapper workflow appropriate for direct invocation from `main` or environment promotion.
- Authenticate to AWS with OIDC.
- Keep package-release workflows intact; runtime deployment must be its own first-class surface.

### 2. Make deploy-output authoritative
Create a machine-readable deploy artifact that includes at minimum:
- git SHA,
- runtime version,
- canonical public base URL,
- stack name,
- region,
- key stack outputs needed by validation.

Do **not** accept a free-text environment URL as the primary authority anymore.

### 3. Bind post-deploy validation to deploy-output
- Update validation workflows so they consume the deploy-output artifact or a reference to it.
- Replace `validation_base_url` as the primary input with deploy-output resolution.
- Keep artifacts immutable and pinned to the deployment that produced them.

### 4. Provenance and integrity
- At minimum, produce `deploy-output.json` and a `sha256` digest.
- Prefer to use **GitHub artifact attestations** where practical for build provenance.
- If the repo already has a signing path that cleanly fits runtime deploy outputs, you may also sign the artifact, but do not build a brittle bespoke system when GitHub provenance features already solve the problem.

### 5. Update workflow contracts and docs together
- Update or create contract schemas for the deploy workflow and deploy-output artifact.
- Rewrite the release runbook and client integration guide so the active story is:
  - repo deploys runtime,
  - repo publishes deploy-output authority,
  - validation consumes that authority.
- Remove active wording that implies runtime deployment happens manually or externally.

### 6. Add workflow tests that enforce the new truth
The tests should fail if:
- runtime deploy workflows disappear again,
- post-deploy validation reverts to free-text URL authority,
- deploy-output schema and workflow inputs/outputs drift,
- legacy CodePipeline/CodeBuild or deleted control-plane paths creep back in.

## Linked issue-closure checklist

- [x] **P0-1:** repo-owned runtime deployment workflow surface exists again.
- [x] **P2-1 (partial):** runtime validation is tied to deploy provenance, not just a URL string.
- [x] **P1-5 (partial):** workflow/release docs tell one truthful story.
- [x] No old CodePipeline/CodeBuild deploy surfaces are reintroduced.
- [x] OIDC is the runtime deploy auth mechanism.

## Success criteria

This session is only complete if all of the following are true:
- there is a reusable runtime deploy workflow in `.github/workflows/`,
- deploy workflows use OIDC,
- deploy-output is machine-readable and authoritative,
- post-deploy validation can resolve and use deploy-output instead of arbitrary base URL input,
- workflow tests validate the new deploy truth,
- release docs and client docs no longer tell users to deploy externally and then paste a URL.

## Verification commands

```bash
uv sync --locked --all-extras --dev
uv run ruff check --fix
uv run ruff format
uv run ruff check
uv run mypy .
uv run pytest tests/infra -q
```

## References to use in this session

## Core current references that should be consulted where relevant

### AWS / GitHub / Python platform docs
- AWS API Gateway: REST vs HTTP APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html
- AWS API Gateway: protect REST APIs with AWS WAF
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html
- AWS API Gateway: disable default endpoint for REST APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-disable-default-endpoint.html
- AWS API Gateway: Regional custom domain names
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-regional-api-custom-domain-create.html
- AWS API Gateway: API mappings for custom domains
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-mappings.html
- AWS API Gateway: integration types
  https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-integration-types.html
- AWS CDK CloudFront behavior defaults
  https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudfront/Behavior.html
- AWS WAF rate-based rules
  https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html
- AWS WAF logging
  https://docs.aws.amazon.com/waf/latest/developerguide/logging.html
- API Gateway logging
  https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html
- Lambda reserved concurrency
  https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html
- Lambda concurrency concepts
  https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html
- S3 abort incomplete multipart uploads
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html
- Step Functions retries and error handling
  https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html
- GitHub Actions OIDC in AWS
  https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- GitHub Actions reusable workflows
  https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows
- GitHub Actions artifact attestations
  https://docs.github.com/en/actions/concepts/security/artifact-attestations
- OpenAI Codex MCP
  https://developers.openai.com/codex/mcp
- OpenAI Codex skills
  https://developers.openai.com/codex/skills/
- OpenAI Docs MCP
  https://developers.openai.com/learn/docs-mcp/
- uv locking and syncing
  https://docs.astral.sh/uv/concepts/projects/sync/
- uv workspaces
  https://docs.astral.sh/uv/concepts/projects/workspaces/
- pytest good practices / importlib mode
  https://docs.pytest.org/en/stable/explanation/goodpractices.html
- FastAPI CORS
  https://fastapi.tiangolo.com/tutorial/cors/
- FastAPI settings / Pydantic settings
  https://fastapi.tiangolo.com/advanced/settings/
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Google Python Style Guide
  https://google.github.io/styleguide/pyguide.html

### AWS / documentation MCP references
- AWS MCP Server user guide
  https://docs.aws.amazon.com/aws-mcp/latest/userguide/what-is-mcp-server.html
- AWS Documentation MCP Server
  https://awslabs.github.io/mcp/servers/aws-documentation-mcp-server
- AWS Knowledge MCP Server
  https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server

### Context7 / Exa
- Context7 GitHub / setup docs
  https://github.com/upstash/context7
- Exa search docs
  https://exa.ai/docs/reference/search-api-guide
  https://exa.ai/docs/reference/search-best-practices

### Upstream runtime examples to inspect only after official docs
- Mangum upstream
  https://github.com/Kludex/mangum
  https://mangum.fastapiexpert.com/
- AWS Lambda Web Adapter upstream
  https://github.com/awslabs/aws-lambda-web-adapter



<!-- FILE: prompts/04-security-observability-capacity-iam.md -->

# Prompt 04 — Add missing production controls: WAF rate limiting, API logging, alarm actions, reserved concurrency, S3 lifecycle, Step Functions retries, and least-privilege IAM

> Status: Completed and deployed live in dev on 2026-03-30. Prompt 04 now uses an explicit low-quota non-prod fallback: this `us-east-1` account remains at `ConcurrentExecutions=10` and `UnreservedConcurrentExecutions=10`, so reserved concurrency is intentionally omitted in non-prod while production remains fail-closed.
>
> Directly closed issue IDs: `P1-3`, `P1-4`, `P2-2`, `P2-3`
>
> Completion summary:
>
> - Added explicit WAF rate limits, API access logging, WAF logging, SNS-backed alarm actions, S3 lifecycle cleanup, explicit Step Functions retries, and task-scoped workflow IAM in the Prompt 04 branch.
> - Replaced the non-prod reserved-concurrency hard requirement with an environment-aware fallback: low-quota non-prod accounts omit reserved concurrency intentionally, while production remains fail-closed.
> - Added synth and workflow-contract tests that assert both the default reserved-concurrency path and the low-quota fallback path.
> - Hardened named observability resources so retained log groups and SNS topics are ensured/imported idempotently instead of breaking deploys.
> - Verified AWS CLI and AWS MCP access, upgraded the CDK bootstrap environment, and deployed the full Prompt 04 control set live to the dev stack.
>
> Verification completed:
>
> - `uv sync --locked --all-extras --dev`
> - `uv run ruff check --fix`
> - `uv run ruff format`
> - `uv run ruff check`
> - `uv run mypy .`
> - `uv run pytest tests/infra -q`
> - `npx aws-cdk synth NovaRuntimeStack ...`
> - `npx aws-cdk bootstrap aws://099060980393/us-east-1 ...`
> - `npx aws-cdk deploy NovaRuntimeStack ...` (fails only on the external Lambda concurrency quota)
> - `aws sts get-caller-identity`
> - `aws apigateway get-stage --rest-api-id sgfeyx9cw2 --stage-name dev --region us-east-1`
> - `aws wafv2 get-web-acl --name NovaRestApiWebAcl-akOLoc7yj9JZ --scope REGIONAL --id 607f4858-c363-49c3-b777-ab71964ffe01 --region us-east-1`
> - `aws cloudwatch describe-alarms --region us-east-1 --alarm-name-prefix NovaRuntimeStack-`
> - `aws lambda get-account-settings --region us-east-1`
> - `aws s3api get-bucket-lifecycle-configuration --bucket novaruntimestack-filetransferbucket22253134-emu8rbt6pdyo --region us-east-1`
> - `aws stepfunctions describe-state-machine --state-machine-arn arn:aws:states:us-east-1:099060980393:stateMachine:ExportWorkflowStateMachineD37E135B-EIrWvK39u190 --region us-east-1`

You are working inside the Nova repository. This is a **security and operations hardening session**. Treat it as productionization work, not cleanup trivia.

## Common execution requirements for every Codex session

### Model and session shape
- Run this in a **fresh Codex session using `gpt-5.4-high`**.
- If your Codex environment supports concurrent helpers, spawn **2-4 focused `gpt-5.4-mini` subagents** for bounded research or file-impact exploration, then reconcile their findings before patching.
- Work on a **clean branch or stacked branch** rooted in the latest completed remediation branch. Do not mix unrelated prompts in one session.

### Mandatory tool and skill choreography
Use these in this order **when available**:

1. **`$aws-architecture` skill**
   Use it at the beginning to sanity-check the target AWS design against current AWS service guidance. Do not let it pull you back toward incremental legacy compatibility if the hard-cut target in this prompt is better.
2. **`$reducing-entropy` skill**
   Use it before design decisions and before the final patch pass. The goal is to delete dead paths, remove toggles, and simplify ownership and authority boundaries.
3. **AWS MCP tooling**
   Prefer the **AWS MCP Server** if configured and authenticated. If that is unavailable, use the **AWS Documentation MCP Server** or **AWS Knowledge MCP Server**. Use it for current AWS docs, CDK/API guidance, and read-only environment inspection when the prompt explicitly calls for it.
4. **Context7**
   Use Context7 for current version-specific docs and code examples for FastAPI, Pydantic, Mangum, uv, pytest, GitHub Actions, and AWS CDK constructs where supported.
5. **`web.run` / browser search**
   Use this whenever MCP coverage is incomplete, when the topic is recency-sensitive, or when you need the latest release notes, migration guides, or product docs. Favor official docs first.
6. **Exa search**
   Use Exa after official docs to find strong upstream implementation examples, reference repositories, or architecture examples. Do not let third-party examples override official product constraints.
7. **`$opensrc-inspect` skill**
   Use it before introducing or retaining upstream dependencies that materially affect runtime or deployment shape (for example Mangum, Lambda Web Adapter, Powertools, or new GitHub Actions helpers). Evaluate maintenance, release freshness, security posture, and issue profile.
8. **`$clean-code` skill**
   Use it before finalizing. The repo should end each session with clearer code, smaller cohesive modules, better naming, and fewer compatibility branches than it started with.

### Fallback rule
If any named tool or skill is unavailable in the Codex environment:
- state that explicitly in your session notes,
- fall back to **official docs via `web.run`** and repo-local inspection,
- continue without asking for permission.

### Code-quality and repo rules
- Use **uv only** for dependency changes, environment sync, and command execution.
- Keep runtime syntax compatible with **Python 3.11+**.
- Use **Ruff** as the formatter/linter and **mypy** as the type gate.
- Keep tests deterministic and isolated; use pytest and existing repo patterns.
- Follow the repo’s **Google-style docstring** convention where public Python APIs or non-trivial scripts are added or changed.
- Prefer deletion and simplification over compatibility toggles or dual-path support.
- Update **docs, contracts, tests, and generated artifacts together** with code changes.
- Never accept “tests pass” as proof that the target state is correct. Re-read the issue checklist at the end.

### Required end-of-session response from Codex
At the end of the session, Codex must provide:
1. a concise summary of what changed,
2. a list of changed files grouped by intent,
3. the issue IDs directly closed,
4. research sources actually consulted,
5. exact verification commands run and their outcomes,
6. residual risk or follow-up items, if any.


## Session-specific objective

Harden the new runtime and ingress architecture so it is defensible and operable:
- WAF rate-based protection,
- API access logging,
- WAF logging,
- alarm actions,
- reserved concurrency defaults,
- S3 lifecycle cleanup for incomplete multipart uploads,
- explicit Step Functions retry/catch strategy,
- task-scoped least-privilege IAM.

## Full issue register for context

# Issue register used across all prompts

Use these stable issue IDs in every Codex session. Treat them as the required acceptance contract for the remediation program.

## [P0] Merge blockers

- **P0-1 — Runtime deployment ownership deleted without replacement.** The repo still owns IaC, contracts, validation, and release docs, but no longer owns runtime deployment. There is no repo-controlled deploy/promotion chain for the live runtime.
- **P0-2 — Current CloudFront API edge cannot serve write traffic.** The surviving CloudFront distribution does not explicitly enable write methods, while the API exposes POST-heavy flows.
- **P0-3 — CloudFront/WAF is bypassable.** The API default execute-api endpoint remains reachable directly, so the supposed protected front door is not authoritative.

## [P1] High-severity design and operational defects

- **P1-1 — Browser/downstream integration has no coherent CORS model.** Browser fetch usage exists, but API Gateway and FastAPI do not form a single explicit CORS contract.
- **P1-2 — Wrong AWS ingress product mix.** The current architecture uses HTTP API plus CloudFront/WAF as a compensation layer instead of the simpler and better-fitting Regional REST API plus direct WAF attachment.
- **P1-3 — Abuse prevention is below production state.** No meaningful WAF rate limiting, stage/route throttling, or bounded public-ingress control plane exists.
- **P1-4 — Observability and forensics are below production state.** No authoritative API access logs, no WAF logs, weak alarm actions, and no single canonical public runtime authority.
- **P1-5 — Docs/specs/runbooks/contracts are internally contradictory.** Active authority still mixes old ECS/Fargate/topology/deploy assumptions with the new serverless branch shape.

## [P2] Important but non-blocking defects

- **P2-1 — Post-deploy validation is too weak.** It proves path reachability, not deployed version, correct environment, auth behavior, CORS, or provenance.
- **P2-2 — Workflow Lambdas are over-privileged.** All task functions receive broad bucket/table permissions instead of task-scoped IAM.
- **P2-3 — Runtime safeguards are missing.** Reserved concurrency, S3 lifecycle cleanup, and bounded operational defaults are missing or under-specified.
- **P2-4 — Tests validate deletions and thin invariants, not production truth.** The suite misses ingress, logging, throttling, IAM, lifecycle, and provenance defects.
- **P2-5 — Runtime path is overcomplicated.** The stack layers API Gateway auth, app auth, Lambda Web Adapter, uvicorn-in-Lambda, and deprecated compatibility shims.

## [P3] Cleanup debt that should be closed during the hard cut

- **P3-1 — Hard-cut cleanup is incomplete.** Deprecated aliases, dead contract generators, and stale docs keep deleted runtime modes and compatibility surfaces alive.

## There are no meaningful [P4] findings in the current review.


## Issue IDs this session must directly close

- **P1-3**
- **P1-4**
- **P2-2**
- **P2-3**

## Issue IDs this session must not regress and should support

- **P1-2** — keep the Regional REST API + direct WAF design from Prompt 01.
- **P1-1** — avoid undoing the unified CORS contract from Prompt 02.
- **P2-1** — make logs and outputs useful to provenance-aware validation and incident response.
- **P2-4** — add synth and runtime tests that assert the hardening controls, not just code presence.
- **P3-1** — avoid leaving placeholder alarm or lifecycle docs that do not match reality.

## Non-negotiable end state for this session

1. The runtime has explicit ingress abuse controls and bounded operational defaults.
2. Access logs and WAF logs exist and are intentionally configured.
3. Alarm actions are wired to a real notification target pattern, not left inert.
4. Workflow/task Lambdas are not all broad read-write clones of one another.
5. Multipart upload cost leaks and unbounded concurrency are explicitly addressed.
6. Step Functions retries are designed intentionally, not left at the platform defaults alone.

## Repo files to read before making changes

Read these first:
- the runtime/ingress stack files created in Prompt 01
- the runtime handler changes from Prompt 02
- `infra/nova_cdk/README.md`
- `tests/infra/test_runtime_stack_contracts.py` or equivalent
- `tests/infra/test_ingress_contracts.py` or equivalent
- `docs/runbooks/RUNBOOK-SERVERLESS-OPERATIONS.md`
- `docs/runbooks/README.md`
- any current observability or alarm-related docs left under `docs/runbooks/`
- the existing Step Functions definition inside the stack

## Mandatory research before coding

1. **AWS MCP / AWS docs**
   - Confirm current guidance and APIs for:
     - WAF rate-based rules,
     - WAF logging,
     - API Gateway REST API access logging,
     - Lambda reserved concurrency,
     - S3 abort incomplete multipart uploads,
     - Step Functions retry policies,
     - IAM least-privilege practices.

2. **Context7**
   - Fetch current docs/examples for relevant CDK v2 Python constructs:
     - WAFv2 rules and logging,
     - API Gateway stage settings/logging,
     - CloudWatch alarms and actions,
     - S3 lifecycle rules,
     - Lambda concurrency properties,
     - DynamoDB/S3/Lambda IAM grants.

3. **`$aws-architecture`**
   - Ask it to review the new runtime shape specifically for:
     - rate limiting,
     - observability,
     - blast radius control,
     - task-role partitioning.

4. **`$opensrc-inspect`**
   - If you are tempted to add new runtime or observability dependencies, inspect them first.
   - Prefer native AWS features and existing repo dependencies over additional libraries.

5. **Exa**
   - Find strong examples only after official docs define the allowed control patterns.

## Recommended `gpt-5.4-mini` subagents

- **mini-1:** WAF + API Gateway logging + alarm-action research with concrete CDK property names.
- **mini-2:** IAM diff analysis: what each workflow Lambda truly needs.
- **mini-3:** S3 lifecycle and Step Functions retry/failure-mode design.

## Files that must be changed in this session

### Existing files that must be edited
- runtime/ingress infra modules from Prompt 01
- any new observability or IAM helper modules from Prompt 01
- `infra/nova_cdk/README.md`
- `docs/runbooks/RUNBOOK-SERVERLESS-OPERATIONS.md`
- `tests/infra/test_runtime_stack_contracts.py`
- `tests/infra/test_ingress_contracts.py`

### New files likely needed
- `infra/nova_cdk/src/nova_cdk/observability.py`
- `infra/nova_cdk/src/nova_cdk/iam.py`
- `tests/infra/test_security_observability_contracts.py` or equivalent
- `tests/infra/test_iam_least_privilege_contracts.py` or equivalent

## Implementation requirements

### 1. Add WAF rate-based protection
- Keep managed rules where useful.
- Add explicit rate-based rules appropriate for a public file-transfer/export API.
- Prefer path-sensitive or route-class-aware controls if your design supports it.
- Document thresholds and rationale.

### 2. Turn on authoritative access logging
- Enable REST API access logs.
- Enable WAF logs.
- Ensure log group naming, retention, and permissions are intentional.
- If CloudFront no longer fronts the API, do not waste time adding CloudFront logging for a deleted API path.

### 3. Wire alarm actions
- Create or use a notification target pattern that can actually fire.
- Do not leave alarms without actions unless a tightly scoped reason is documented.
- Favor a clean SNS-based pattern or another standard AWS notification path.

### 4. Add reserved concurrency defaults
- Set reserved concurrency for API and workflow Lambdas based on sensible blast-radius goals.
- Make the configuration intentional and explainable.
- Do not leave all functions unbounded.

### 5. Add S3 lifecycle rules
- Abort incomplete multipart uploads automatically.
- Clean transient prefixes where appropriate.
- Preserve durable exported artifacts where required by product behavior.

### 6. Tighten IAM by task role
- Split workflow task permissions by actual responsibility.
- Avoid the current pattern where validate/copy/finalize/fail all get broad bucket/table mutation rights.
- Preserve functionality while shrinking privilege.

### 7. Improve Step Functions retry semantics
- Add explicit retries/backoff/jitter where domain-transient failures justify them.
- Keep failure recording deterministic.
- Do not rely solely on default integration error behavior.

### 8. Test the hardening controls
Add synth assertions that fail if:
- WAF rate rules vanish,
- logging vanishes,
- alarms have no actions,
- reserved concurrency is missing,
- S3 lifecycle cleanup is missing,
- broad IAM grants return.

## Linked issue-closure checklist

- [x] **P1-3:** ingress abuse controls exist and are test-enforced.
- [x] **P1-4:** authoritative logs and alarm actions exist and are test-enforced.
- [x] **P2-2:** workflow/task IAM is scoped by responsibility.
- [x] **P2-3:** concurrency policy and S3 lifecycle safeguards are implemented, test-enforced, and deployed live. Low-quota non-prod omits reserved concurrency intentionally; production remains fail-closed.
- [x] Step Functions retry/error behavior is explicit and justified.

## Success criteria

This session is only complete if all of the following are true:
- WAF includes rate-based protection,
- REST API access logging is enabled,
- WAF logging is enabled,
- alarm actions are wired,
- Lambda reserved concurrency exists for the key functions,
- S3 lifecycle includes abort-incomplete-multipart-upload behavior,
- IAM scopes are visibly narrower than before this session,
- synth tests prove those controls exist.

## Verification commands

```bash
uv sync --locked --all-extras --dev
uv run ruff check --fix
uv run ruff format
uv run ruff check
uv run mypy .
uv run pytest tests/infra -q
uv run --package nova-cdk cdk synth   -c account=111111111111   -c region=us-west-2   -c environment=dev   -c jwt_issuer=https://issuer.example.com/   -c jwt_audience=api://nova   -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json   -c api_domain_name=api.dev.example.com   -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000
```

## References to use in this session

## Core current references that should be consulted where relevant

### AWS / GitHub / Python platform docs
- AWS API Gateway: REST vs HTTP APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html
- AWS API Gateway: protect REST APIs with AWS WAF
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html
- AWS API Gateway: disable default endpoint for REST APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-disable-default-endpoint.html
- AWS API Gateway: Regional custom domain names
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-regional-api-custom-domain-create.html
- AWS API Gateway: API mappings for custom domains
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-mappings.html
- AWS API Gateway: integration types
  https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-integration-types.html
- AWS CDK CloudFront behavior defaults
  https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudfront/Behavior.html
- AWS WAF rate-based rules
  https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html
- AWS WAF logging
  https://docs.aws.amazon.com/waf/latest/developerguide/logging.html
- API Gateway logging
  https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html
- Lambda reserved concurrency
  https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html
- Lambda concurrency concepts
  https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html
- S3 abort incomplete multipart uploads
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html
- Step Functions retries and error handling
  https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html
- GitHub Actions OIDC in AWS
  https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- GitHub Actions reusable workflows
  https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows
- GitHub Actions artifact attestations
  https://docs.github.com/en/actions/concepts/security/artifact-attestations
- OpenAI Codex MCP
  https://developers.openai.com/codex/mcp
- OpenAI Codex skills
  https://developers.openai.com/codex/skills/
- OpenAI Docs MCP
  https://developers.openai.com/learn/docs-mcp/
- uv locking and syncing
  https://docs.astral.sh/uv/concepts/projects/sync/
- uv workspaces
  https://docs.astral.sh/uv/concepts/projects/workspaces/
- pytest good practices / importlib mode
  https://docs.pytest.org/en/stable/explanation/goodpractices.html
- FastAPI CORS
  https://fastapi.tiangolo.com/tutorial/cors/
- FastAPI settings / Pydantic settings
  https://fastapi.tiangolo.com/advanced/settings/
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Google Python Style Guide
  https://google.github.io/styleguide/pyguide.html

### AWS / documentation MCP references
- AWS MCP Server user guide
  https://docs.aws.amazon.com/aws-mcp/latest/userguide/what-is-mcp-server.html
- AWS Documentation MCP Server
  https://awslabs.github.io/mcp/servers/aws-documentation-mcp-server
- AWS Knowledge MCP Server
  https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server

### Context7 / Exa
- Context7 GitHub / setup docs
  https://github.com/upstash/context7
- Exa search docs
  https://exa.ai/docs/reference/search-api-guide
  https://exa.ai/docs/reference/search-best-practices

### Upstream runtime examples to inspect only after official docs
- Mangum upstream
  https://github.com/Kludex/mangum
  https://mangum.fastapiexpert.com/
- AWS Lambda Web Adapter upstream
  https://github.com/awslabs/aws-lambda-web-adapter

---

## Session Completion

Status: completed in branch on 2026-03-30

Directly closed in this session:

- `P1-3`
- `P1-4`
- `P2-2`
- `P2-3`

Implemented outcomes:

- Added WAF managed rules plus explicit global and write-path rate limits for the Regional REST API ingress.
- Added authoritative API Gateway access logs, WAF log delivery, and SNS-backed alarm actions.
- Tightened workflow IAM to task-scoped table and bucket permissions instead of broad cloned grants.
- Added S3 lifecycle cleanup for incomplete multipart uploads and transient `tmp/` objects.
- Added explicit Step Functions retry, timeout, jitter, and catch behavior.
- Added synth tests for ingress hardening, observability, IAM narrowing, and lifecycle controls.
- Fixed the WAF logging CloudFormation payload to emit the AWS-required `DefaultBehavior`, `Filters`, and `Name` keys.
- Added an environment-aware concurrency policy so low-quota non-prod accounts intentionally omit reserved concurrency while production remains fail-closed.
- Hardened named observability resources so existing log groups and SNS topics no longer break deploys.
- Deployed the full Prompt 04 stack update live to the dev stack with `ENABLE_RESERVED_CONCURRENCY=false` in this low-quota account.

Verification completed:

- `uv sync --locked --all-extras --dev`
- `uv run ruff check --fix`
- `uv run ruff format`
- `uv run ruff check`
- `uv run mypy .`
- `uv run pytest tests/infra -q`
- `npx aws-cdk synth NovaRuntimeStack ...`
- `npx aws-cdk bootstrap aws://099060980393/us-east-1 ...`
- `npx aws-cdk deploy NovaRuntimeStack ...`
- `aws sts get-caller-identity`
- `aws apigateway get-stage --rest-api-id sgfeyx9cw2 --stage-name dev --region us-east-1`
- `aws wafv2 get-web-acl --name NovaRestApiWebAcl-akOLoc7yj9JZ --scope REGIONAL --id 607f4858-c363-49c3-b777-ab71964ffe01 --region us-east-1`
- `aws cloudwatch describe-alarms --region us-east-1 --alarm-name-prefix NovaRuntimeStack-`
- `aws lambda get-account-settings --region us-east-1`
- `aws s3api get-bucket-lifecycle-configuration --bucket novaruntimestack-filetransferbucket22253134-emu8rbt6pdyo --region us-east-1`
- `aws stepfunctions describe-state-machine --state-machine-arn arn:aws:states:us-east-1:099060980393:stateMachine:ExportWorkflowStateMachineD37E135B-EIrWvK39u190 --region us-east-1`
- `aws service-quotas request-service-quota-increase --service-code lambda --quota-code L-B99A9384 --desired-value 1001 --region us-east-1`
- `aws service-quotas get-requested-service-quota-change --request-id db01555c4d7d4db8a299e58b4a0107c0BLIqg8qP --region us-east-1`

Prompt-04-scoped residuals:

- The account-wide Lambda concurrency quota in `us-east-1` is still `10`, so non-prod continues to rely on the new fallback path and cannot enforce reserved concurrency in this account.
- Production still depends on an account with enough concurrency headroom because the canonical end state remains fail-closed for production reserved concurrency.



<!-- FILE: prompts/05-validation-tests-docs-authority-cleanup.md -->

# Prompt 05 — Rebuild validation truth, expand tests to production reality, rewrite docs authority, and finish hard-cut cleanup

You are working inside the Nova repository. This is the **truth-restoration session**. Its job is to make the repo’s tests, docs, contracts, and validation mechanisms describe the system that now actually exists.

## Common execution requirements for every Codex session

### Model and session shape
- Run this in a **fresh Codex session using `gpt-5.4-high`**.
- If your Codex environment supports concurrent helpers, spawn **2-4 focused `gpt-5.4-mini` subagents** for bounded research or file-impact exploration, then reconcile their findings before patching.
- Work on a **clean branch or stacked branch** rooted in the latest completed remediation branch. Do not mix unrelated prompts in one session.

### Mandatory tool and skill choreography
Use these in this order **when available**:

1. **`$aws-architecture` skill**
   Use it at the beginning to sanity-check the target AWS design against current AWS service guidance. Do not let it pull you back toward incremental legacy compatibility if the hard-cut target in this prompt is better.
2. **`$reducing-entropy` skill**
   Use it before design decisions and before the final patch pass. The goal is to delete dead paths, remove toggles, and simplify ownership and authority boundaries.
3. **AWS MCP tooling**
   Prefer the **AWS MCP Server** if configured and authenticated. If that is unavailable, use the **AWS Documentation MCP Server** or **AWS Knowledge MCP Server**. Use it for current AWS docs, CDK/API guidance, and read-only environment inspection when the prompt explicitly calls for it.
4. **Context7**
   Use Context7 for current version-specific docs and code examples for FastAPI, Pydantic, Mangum, uv, pytest, GitHub Actions, and AWS CDK constructs where supported.
5. **`web.run` / browser search**
   Use this whenever MCP coverage is incomplete, when the topic is recency-sensitive, or when you need the latest release notes, migration guides, or product docs. Favor official docs first.
6. **Exa search**
   Use Exa after official docs to find strong upstream implementation examples, reference repositories, or architecture examples. Do not let third-party examples override official product constraints.
7. **`$opensrc-inspect` skill**
   Use it before introducing or retaining upstream dependencies that materially affect runtime or deployment shape (for example Mangum, Lambda Web Adapter, Powertools, or new GitHub Actions helpers). Evaluate maintenance, release freshness, security posture, and issue profile.
8. **`$clean-code` skill**
   Use it before finalizing. The repo should end each session with clearer code, smaller cohesive modules, better naming, and fewer compatibility branches than it started with.

### Fallback rule
If any named tool or skill is unavailable in the Codex environment:
- state that explicitly in your session notes,
- fall back to **official docs via `web.run`** and repo-local inspection,
- continue without asking for permission.

### Code-quality and repo rules
- Use **uv only** for dependency changes, environment sync, and command execution.
- Keep runtime syntax compatible with **Python 3.11+**.
- Use **Ruff** as the formatter/linter and **mypy** as the type gate.
- Keep tests deterministic and isolated; use pytest and existing repo patterns.
- Follow the repo’s **Google-style docstring** convention where public Python APIs or non-trivial scripts are added or changed.
- Prefer deletion and simplification over compatibility toggles or dual-path support.
- Update **docs, contracts, tests, and generated artifacts together** with code changes.
- Never accept “tests pass” as proof that the target state is correct. Re-read the issue checklist at the end.

### Required end-of-session response from Codex
At the end of the session, Codex must provide:
1. a concise summary of what changed,
2. a list of changed files grouped by intent,
3. the issue IDs directly closed,
4. research sources actually consulted,
5. exact verification commands run and their outcomes,
6. residual risk or follow-up items, if any.


## Session-specific objective

Finish the hard cut by:
- replacing route-reachability validation with provenance-aware runtime validation,
- expanding tests so they enforce production truth instead of deleted-surface absence,
- rewriting active docs/specs/runbooks/contracts so they are internally consistent,
- deleting or regenerating dead contract artifacts and compatibility leftovers.

## Full issue register for context

# Issue register used across all prompts

Use these stable issue IDs in every Codex session. Treat them as the required acceptance contract for the remediation program.

## [P0] Merge blockers

- **P0-1 — Runtime deployment ownership deleted without replacement.** The repo still owns IaC, contracts, validation, and release docs, but no longer owns runtime deployment. There is no repo-controlled deploy/promotion chain for the live runtime.
- **P0-2 — Current CloudFront API edge cannot serve write traffic.** The surviving CloudFront distribution does not explicitly enable write methods, while the API exposes POST-heavy flows.
- **P0-3 — CloudFront/WAF is bypassable.** The API default execute-api endpoint remains reachable directly, so the supposed protected front door is not authoritative.

## [P1] High-severity design and operational defects

- **P1-1 — Browser/downstream integration has no coherent CORS model.** Browser fetch usage exists, but API Gateway and FastAPI do not form a single explicit CORS contract.
- **P1-2 — Wrong AWS ingress product mix.** The current architecture uses HTTP API plus CloudFront/WAF as a compensation layer instead of the simpler and better-fitting Regional REST API plus direct WAF attachment.
- **P1-3 — Abuse prevention is below production state.** No meaningful WAF rate limiting, stage/route throttling, or bounded public-ingress control plane exists.
- **P1-4 — Observability and forensics are below production state.** No authoritative API access logs, no WAF logs, weak alarm actions, and no single canonical public runtime authority.
- **P1-5 — Docs/specs/runbooks/contracts are internally contradictory.** Active authority still mixes old ECS/Fargate/topology/deploy assumptions with the new serverless branch shape.

## [P2] Important but non-blocking defects

- **P2-1 — Post-deploy validation is too weak.** It proves path reachability, not deployed version, correct environment, auth behavior, CORS, or provenance.
- **P2-2 — Workflow Lambdas are over-privileged.** All task functions receive broad bucket/table permissions instead of task-scoped IAM.
- **P2-3 — Runtime safeguards are missing.** Reserved concurrency, S3 lifecycle cleanup, and bounded operational defaults are missing or under-specified.
- **P2-4 — Tests validate deletions and thin invariants, not production truth.** The suite misses ingress, logging, throttling, IAM, lifecycle, and provenance defects.
- **P2-5 — Runtime path is overcomplicated.** The stack layers API Gateway auth, app auth, Lambda Web Adapter, uvicorn-in-Lambda, and deprecated compatibility shims.

## [P3] Cleanup debt that should be closed during the hard cut

- **P3-1 — Hard-cut cleanup is incomplete.** Deprecated aliases, dead contract generators, and stale docs keep deleted runtime modes and compatibility surfaces alive.

## There are no meaningful [P4] findings in the current review.


## Issue IDs this session must directly close

- **P1-5**
- **P2-1** (remaining validation and runtime-truth half)
- **P2-4**
- **P3-1**

## Issue IDs this session must not regress and should verify

- **P0-1** — runtime deploy ownership must remain repo-owned.
- **P0-2 / P0-3 / P1-2** — ingress truth must remain REST API + direct WAF + custom domain authority.
- **P1-1** — CORS contract from Prompt 02 must remain explicit and test-covered.
- **P1-3 / P1-4 / P2-2 / P2-3** — hardening controls from Prompt 04 must remain asserted.

## Non-negotiable end state for this session

1. Active docs, active tests, and active validation scripts all describe the same platform.
2. Post-deploy validation proves the right deployment and version, not just “something answered at a URL.”
3. Tests fail on drift in ingress, logging, throttling, IAM, lifecycle, provenance, and doc authority.
4. Dead runtime-config contract surfaces and compatibility aliases are removed or regenerated out of existence.
5. Downstream guidance stops telling consumers to hard-code runtime authority that the repo should publish.

## Repo files to read before making changes

Read these first:
- `scripts/release/validate_route_contract.py`
- any deploy-output or validation scripts added in Prompt 03
- `scripts/release/runtime_config_contract.py`
- `docs/release/runtime-config-contract.generated.md`
- `tests/infra/test_docs_authority_contracts.py`
- `tests/infra/test_release_workflow_contracts.py`
- `tests/infra/test_workflow_contract_docs.py`
- `scripts/checks/run_infra_contracts.sh`
- `README.md`
- `AGENTS.md`
- `docs/README.md`
- `docs/overview/ACTIVE-DOCS-INDEX.md`
- `docs/architecture/README.md`
- `docs/contracts/README.md`
- `docs/runbooks/README.md`
- `docs/release/README.md`
- `docs/clients/post-deploy-validation-integration-guide.md`
- active ADR/spec/runbook files that still describe the old serverless baseline or deleted deploy authority

## Mandatory research before coding

1. **`$reducing-entropy`**
   - Use it to identify every now-dead doc, contract, generator, or test that still preserves the old story.

2. **Context7**
   - Reconfirm current uv, pytest, FastAPI, and Pydantic guidance where validation/test/doc generation patterns matter.

3. **GitHub docs / web.run**
   - Reconfirm workflow-call and artifact-attestation behaviors if the docs/contracts refer to them directly.

4. **AWS MCP / AWS docs**
   - Use when validation or docs need fresh wording about API Gateway custom domains, endpoint disabling, logging, or WAF.

5. **Exa**
   - Use sparingly for strong examples of provenance-aware validation or doc authority models, only after official docs.

## Recommended `gpt-5.4-mini` subagents

- **mini-1:** docs-authority router audit — every active doc that still lies.
- **mini-2:** validation/test audit — every missing assertion against the new target state.
- **mini-3:** runtime-config contract audit — every generated artifact or schema still modeling deleted paths.

## Files that must be changed in this session

### Existing files that must be edited or deleted
- `scripts/release/validate_route_contract.py`
  Replace or radically narrow it; do not leave it as the primary post-deploy truth gate.
- `scripts/release/runtime_config_contract.py`
- `docs/release/runtime-config-contract.generated.md`
- `tests/infra/test_docs_authority_contracts.py`
- `tests/infra/test_release_workflow_contracts.py`
- `tests/infra/test_workflow_contract_docs.py`
- `scripts/checks/run_infra_contracts.sh`
- `README.md`
- `AGENTS.md`
- `docs/README.md`
- `docs/overview/ACTIVE-DOCS-INDEX.md`
- `docs/architecture/README.md`
- `docs/contracts/README.md`
- `docs/runbooks/README.md`
- `docs/release/README.md`
- `docs/clients/post-deploy-validation-integration-guide.md`

### New files likely needed
- `tests/infra/test_deploy_output_contracts.py` if not already added in Prompt 03
- `tests/infra/test_runtime_validation_contracts.py`
- `tests/infra/test_docs_router_truth.py` or equivalent if a split makes sense
- replacement generated docs for runtime deploy/public-base-url authority if needed

### Active docs likely needing updates or archival
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `docs/architecture/spec/SPEC-0029-platform-serverless.md`
- any active spec/ADR that still claims:
  - HTTP API + CloudFront/WAF,
  - Lambda Web Adapter as the runtime path,
  - manual/external deployment,
  - old SSM/runtime-base-url authority,
  - deleted worker/service template contract shapes.

## Implementation requirements

### 1. Replace weak route-only validation with deploy-aware validation
The new validation path must:
- resolve the deploy-output authority artifact,
- hit the canonical public base URL from that artifact,
- verify `/v1/releases/info` matches expected deployed version and/or SHA,
- validate health/readiness,
- validate at least one protected-route golden flow,
- validate CORS preflight where browser clients matter,
- keep legacy-route 404 checks only where they still serve a real contract purpose.

### 2. Expand tests to assert production truth
The test suite must cover:
- ingress shape,
- custom-domain authority,
- disabled default endpoint,
- WAF/logging/throttling/concurrency/lifecycle/IAM controls,
- deploy-output schema,
- workflow contracts,
- doc authority routing,
- generated docs freshness where applicable.

### 3. Rewrite active docs so they tell one story
- Update all top-level routers to point to the real active authority.
- Archive or supersede active-but-false docs.
- Remove wording that says “target state” for things that are now implemented.
- Remove wording that says “manual or external deployment” if the repo now deploys runtime itself.
- Downstream consumer docs must describe published deploy-output authority, not free-text `NOVA_API_BASE_URL` configuration as the primary mechanism.

### 4. Regenerate or delete dead contract artifacts
- Update `runtime_config_contract.py` so it only documents living runtime surfaces.
- Remove dead worker/service template assumptions that no longer exist.
- Regenerate any checked-in generated docs that are still active.

### 5. Replace deletion-enforcement tests with truth-enforcement tests
- It is acceptable to keep a few tests that ensure deleted legacy paths stay deleted.
- It is not acceptable for the suite to mostly test absence while ignoring the new production truth.
- Bias toward tests that would catch a real regression in architecture, deployment, or operations.

## Linked issue-closure checklist

- [ ] **P1-5:** active docs/specs/runbooks/contracts are internally consistent.
- [ ] **P2-1:** runtime validation proves the right deployed runtime, not just route reachability.
- [ ] **P2-4:** tests assert production truth across ingress, provenance, logging, throttling, IAM, lifecycle, and docs authority.
- [ ] **P3-1:** dead contract generators, aliases, and stale docs are removed or regenerated.
- [ ] Consumer docs stop treating a manually configured base URL as the source of runtime authority.

## Success criteria

This session is only complete if all of the following are true:
- route-only validation is no longer the primary release truth gate,
- active docs no longer conflict with each other about platform shape or deployment authority,
- runtime-config generated docs describe only living surfaces,
- tests would fail if someone reintroduced the old platform story,
- the repo’s top-level routers send readers to one real authority set.

## Verification commands

```bash
uv sync --locked --all-extras --dev
uv run ruff check --fix
uv run ruff format
uv run ruff check
uv run mypy .
uv run pytest tests/infra -q
uv run pytest packages/nova_file_api/tests -q
```

## References to use in this session

## Core current references that should be consulted where relevant

### AWS / GitHub / Python platform docs
- AWS API Gateway: REST vs HTTP APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html
- AWS API Gateway: protect REST APIs with AWS WAF
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html
- AWS API Gateway: disable default endpoint for REST APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-disable-default-endpoint.html
- AWS API Gateway: Regional custom domain names
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-regional-api-custom-domain-create.html
- AWS API Gateway: API mappings for custom domains
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-mappings.html
- AWS API Gateway: integration types
  https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-integration-types.html
- AWS CDK CloudFront behavior defaults
  https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudfront/Behavior.html
- AWS WAF rate-based rules
  https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html
- AWS WAF logging
  https://docs.aws.amazon.com/waf/latest/developerguide/logging.html
- API Gateway logging
  https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html
- Lambda reserved concurrency
  https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html
- Lambda concurrency concepts
  https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html
- S3 abort incomplete multipart uploads
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html
- Step Functions retries and error handling
  https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html
- GitHub Actions OIDC in AWS
  https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- GitHub Actions reusable workflows
  https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows
- GitHub Actions artifact attestations
  https://docs.github.com/en/actions/concepts/security/artifact-attestations
- OpenAI Codex MCP
  https://developers.openai.com/codex/mcp
- OpenAI Codex skills
  https://developers.openai.com/codex/skills/
- OpenAI Docs MCP
  https://developers.openai.com/learn/docs-mcp/
- uv locking and syncing
  https://docs.astral.sh/uv/concepts/projects/sync/
- uv workspaces
  https://docs.astral.sh/uv/concepts/projects/workspaces/
- pytest good practices / importlib mode
  https://docs.pytest.org/en/stable/explanation/goodpractices.html
- FastAPI CORS
  https://fastapi.tiangolo.com/tutorial/cors/
- FastAPI settings / Pydantic settings
  https://fastapi.tiangolo.com/advanced/settings/
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Google Python Style Guide
  https://google.github.io/styleguide/pyguide.html

### AWS / documentation MCP references
- AWS MCP Server user guide
  https://docs.aws.amazon.com/aws-mcp/latest/userguide/what-is-mcp-server.html
- AWS Documentation MCP Server
  https://awslabs.github.io/mcp/servers/aws-documentation-mcp-server
- AWS Knowledge MCP Server
  https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server

### Context7 / Exa
- Context7 GitHub / setup docs
  https://github.com/upstash/context7
- Exa search docs
  https://exa.ai/docs/reference/search-api-guide
  https://exa.ai/docs/reference/search-best-practices

### Upstream runtime examples to inspect only after official docs
- Mangum upstream
  https://github.com/Kludex/mangum
  https://mangum.fastapiexpert.com/
- AWS Lambda Web Adapter upstream
  https://github.com/awslabs/aws-lambda-web-adapter



<!-- FILE: prompts/99-final-critical-review-and-finish.md -->

# Prompt 99 — Final critical review, verification, and finish-anything-left session

You are working inside the fully remediated Nova repository after Prompts 01-05 have been applied. This is **not** a passive review. It is a critical verification-and-fix session. You must inspect the repo as an external principal architect and finish any remaining work needed to reach the intended target state.

## Common execution requirements for every Codex session

### Model and session shape
- Run this in a **fresh Codex session using `gpt-5.4-high`**.
- If your Codex environment supports concurrent helpers, spawn **2-4 focused `gpt-5.4-mini` subagents** for bounded research or file-impact exploration, then reconcile their findings before patching.
- Work on a **clean branch or stacked branch** rooted in the latest completed remediation branch. Do not mix unrelated prompts in one session.

### Mandatory tool and skill choreography
Use these in this order **when available**:

1. **`$aws-architecture` skill**
   Use it at the beginning to sanity-check the target AWS design against current AWS service guidance. Do not let it pull you back toward incremental legacy compatibility if the hard-cut target in this prompt is better.
2. **`$reducing-entropy` skill**
   Use it before design decisions and before the final patch pass. The goal is to delete dead paths, remove toggles, and simplify ownership and authority boundaries.
3. **AWS MCP tooling**
   Prefer the **AWS MCP Server** if configured and authenticated. If that is unavailable, use the **AWS Documentation MCP Server** or **AWS Knowledge MCP Server**. Use it for current AWS docs, CDK/API guidance, and read-only environment inspection when the prompt explicitly calls for it.
4. **Context7**
   Use Context7 for current version-specific docs and code examples for FastAPI, Pydantic, Mangum, uv, pytest, GitHub Actions, and AWS CDK constructs where supported.
5. **`web.run` / browser search**
   Use this whenever MCP coverage is incomplete, when the topic is recency-sensitive, or when you need the latest release notes, migration guides, or product docs. Favor official docs first.
6. **Exa search**
   Use Exa after official docs to find strong upstream implementation examples, reference repositories, or architecture examples. Do not let third-party examples override official product constraints.
7. **`$opensrc-inspect` skill**
   Use it before introducing or retaining upstream dependencies that materially affect runtime or deployment shape (for example Mangum, Lambda Web Adapter, Powertools, or new GitHub Actions helpers). Evaluate maintenance, release freshness, security posture, and issue profile.
8. **`$clean-code` skill**
   Use it before finalizing. The repo should end each session with clearer code, smaller cohesive modules, better naming, and fewer compatibility branches than it started with.

### Fallback rule
If any named tool or skill is unavailable in the Codex environment:
- state that explicitly in your session notes,
- fall back to **official docs via `web.run`** and repo-local inspection,
- continue without asking for permission.

### Code-quality and repo rules
- Use **uv only** for dependency changes, environment sync, and command execution.
- Keep runtime syntax compatible with **Python 3.11+**.
- Use **Ruff** as the formatter/linter and **mypy** as the type gate.
- Keep tests deterministic and isolated; use pytest and existing repo patterns.
- Follow the repo’s **Google-style docstring** convention where public Python APIs or non-trivial scripts are added or changed.
- Prefer deletion and simplification over compatibility toggles or dual-path support.
- Update **docs, contracts, tests, and generated artifacts together** with code changes.
- Never accept “tests pass” as proof that the target state is correct. Re-read the issue checklist at the end.

### Required end-of-session response from Codex
At the end of the session, Codex must provide:
1. a concise summary of what changed,
2. a list of changed files grouped by intent,
3. the issue IDs directly closed,
4. research sources actually consulted,
5. exact verification commands run and their outcomes,
6. residual risk or follow-up items, if any.


## Session-specific objective

Perform an end-to-end critical review of the repository and:
- verify that every issue ID from the review is actually closed,
- detect any residual design drift, missing files, stale docs, weak tests, bad defaults, or incomplete cleanup,
- patch anything still wrong,
- then re-run the validation matrix.

Do not stop at obvious checks. Assume earlier sessions may have landed partial work, locally passing tests, or inconsistent docs.

## Full issue register to verify

# Issue register used across all prompts

Use these stable issue IDs in every Codex session. Treat them as the required acceptance contract for the remediation program.

## [P0] Merge blockers

- **P0-1 — Runtime deployment ownership deleted without replacement.** The repo still owns IaC, contracts, validation, and release docs, but no longer owns runtime deployment. There is no repo-controlled deploy/promotion chain for the live runtime.
- **P0-2 — Current CloudFront API edge cannot serve write traffic.** The surviving CloudFront distribution does not explicitly enable write methods, while the API exposes POST-heavy flows.
- **P0-3 — CloudFront/WAF is bypassable.** The API default execute-api endpoint remains reachable directly, so the supposed protected front door is not authoritative.

## [P1] High-severity design and operational defects

- **P1-1 — Browser/downstream integration has no coherent CORS model.** Browser fetch usage exists, but API Gateway and FastAPI do not form a single explicit CORS contract.
- **P1-2 — Wrong AWS ingress product mix.** The current architecture uses HTTP API plus CloudFront/WAF as a compensation layer instead of the simpler and better-fitting Regional REST API plus direct WAF attachment.
- **P1-3 — Abuse prevention is below production state.** No meaningful WAF rate limiting, stage/route throttling, or bounded public-ingress control plane exists.
- **P1-4 — Observability and forensics are below production state.** No authoritative API access logs, no WAF logs, weak alarm actions, and no single canonical public runtime authority.
- **P1-5 — Docs/specs/runbooks/contracts are internally contradictory.** Active authority still mixes old ECS/Fargate/topology/deploy assumptions with the new serverless branch shape.

## [P2] Important but non-blocking defects

- **P2-1 — Post-deploy validation is too weak.** It proves path reachability, not deployed version, correct environment, auth behavior, CORS, or provenance.
- **P2-2 — Workflow Lambdas are over-privileged.** All task functions receive broad bucket/table permissions instead of task-scoped IAM.
- **P2-3 — Runtime safeguards are missing.** Reserved concurrency, S3 lifecycle cleanup, and bounded operational defaults are missing or under-specified.
- **P2-4 — Tests validate deletions and thin invariants, not production truth.** The suite misses ingress, logging, throttling, IAM, lifecycle, and provenance defects.
- **P2-5 — Runtime path is overcomplicated.** The stack layers API Gateway auth, app auth, Lambda Web Adapter, uvicorn-in-Lambda, and deprecated compatibility shims.

## [P3] Cleanup debt that should be closed during the hard cut

- **P3-1 — Hard-cut cleanup is incomplete.** Deprecated aliases, dead contract generators, and stale docs keep deleted runtime modes and compatibility surfaces alive.

## There are no meaningful [P4] findings in the current review.


## Review standard

You are reviewing for:
- correctness,
- architectural coherence,
- operational readiness,
- authority-model truth,
- security,
- maintainability,
- reduction of entropy.

Do not defer to the repo’s current shape if a remaining hard-cut cleanup is still better.

## Mandatory tools and research

Use all of the following where available:

1. **`$aws-architecture`**
   - Re-review the final AWS architecture and call out any residual over-complexity or hidden bypass.
2. **`$reducing-entropy`**
   - Ask it to identify any remaining dead code, stale contracts, unnecessary toggles, or duplicate layers.
3. **`$clean-code`**
   - Use it before the final patch pass.
4. **AWS MCP / AWS Documentation MCP**
   - Reconfirm any still-uncertain AWS behavior or service constraints.
5. **Context7**
   - Reconfirm any library/tooling behavior you are about to rely on.
6. **Exa**
   - Use only if you need strong upstream examples to settle a remaining implementation choice.
7. **`web.run`**
   - Use for all remaining recency-sensitive facts and official docs.

## Recommended `gpt-5.4-mini` subagents

Spawn at least these if supported:
- **mini-1:** architecture and AWS infra verification against the issue register.
- **mini-2:** workflows/provenance/contracts/docs authority verification.
- **mini-3:** runtime/tests/CORS/auth verification.
- **mini-4:** dead code and stale file detection across the repo.

Have each subagent return:
- issue IDs checked,
- evidence,
- suspected remaining defects,
- file paths,
- suggested fixes.

Then reconcile all of that in the main session before patching.

## Required verification checklist

You must explicitly verify each item below and fix failures you find.

### Ingress / architecture
- [ ] No API CloudFront path remains unless there is a separately justified non-API CDN need.
- [ ] API Gateway public ingress is REST API, not HTTP API.
- [ ] Default execute-api endpoint is disabled.
- [ ] One canonical public base URL exists and is documented.
- [ ] WAF is attached directly and regionally to the API stage.
- [ ] The stack no longer hard-requires `us-east-1`.

### Runtime path
- [ ] FastAPI is still the contract engine.
- [ ] Production Lambda no longer uses uvicorn-in-Lambda.
- [ ] Production Lambda no longer depends on Lambda Web Adapter.
- [ ] Native Lambda handler path is present and tested.
- [ ] OpenAPI export/generation still works.

### Browser contract
- [ ] CORS is explicit and tested.
- [ ] S3 and API/browser contract assumptions align.

### Deployment authority and provenance
- [ ] Repo-owned runtime deployment workflows exist.
- [ ] OIDC is used for runtime deploys.
- [ ] Deploy-output authority artifact exists and is schema-backed.
- [ ] Post-deploy validation consumes deploy-output authority, not arbitrary URL strings.
- [ ] Release and client docs describe the same deploy/validation story.

### Security / ops
- [ ] WAF rate-based rules exist.
- [ ] API access logs exist.
- [ ] WAF logs exist.
- [ ] Alarm actions are wired.
- [ ] Reserved concurrency exists for key Lambdas.
- [ ] S3 lifecycle aborts incomplete multipart uploads.
- [ ] Workflow/task IAM is scoped by responsibility.
- [ ] Step Functions retries are explicit and justified.

### Tests / docs / cleanup
- [ ] Infra tests assert production truth, not mostly absence of deleted surfaces.
- [ ] Active docs/routes/specs/runbooks are internally consistent.
- [ ] Dead compatibility aliases and dead contract generators are gone or regenerated away.
- [ ] No active doc still describes manual/external runtime deploy as the main path.
- [ ] No active doc still describes HTTP API + CloudFront/WAF + Lambda Web Adapter as the live target.

## Files to inspect regardless of whether you change them

- `infra/nova_cdk/**`
- `.github/workflows/**`
- `.github/actions/**`
- `packages/nova_file_api/**`
- `tests/infra/**`
- `packages/nova_file_api/tests/**`
- `scripts/release/**`
- `docs/README.md`
- `docs/overview/ACTIVE-DOCS-INDEX.md`
- `docs/architecture/**`
- `docs/contracts/**`
- `docs/runbooks/**`
- `docs/release/**`
- `docs/clients/**`

## Required end-of-session output

Your final response in the Codex session must include:
1. **Issue closure table**
   Every issue ID from the register above must be marked:
   - closed with evidence,
   - partially closed with remaining action,
   - or still open.
2. **Changed files grouped by theme**
3. **Remaining risks**
4. **Verification command transcript summary**
5. **Any follow-up items that should become a new prompt**
   Only include this if something truly could not be responsibly finished in the session.

## Verification commands

Run the broadest practical matrix. If you rename tests or scripts, run the updated equivalents and say so.

```bash
uv sync --locked --all-extras --dev
uv run ruff check --fix
uv run ruff format
uv run ruff check
uv run mypy .
uv run pytest -q
uv run python scripts/contracts/export_openapi.py --check
uv run python scripts/release/generate_clients.py --check
uv run python scripts/release/generate_python_clients.py --check
uv run --package nova-cdk cdk synth   -c account=111111111111   -c region=us-west-2   -c environment=dev   -c jwt_issuer=https://issuer.example.com/   -c jwt_audience=api://nova   -c jwt_jwks_url=https://issuer.example.com/.well-known/jwks.json   -c api_domain_name=api.dev.example.com   -c certificate_arn=arn:aws:acm:us-west-2:111111111111:certificate/00000000-0000-0000-0000-000000000000
```

## References to use in this session

## Core current references that should be consulted where relevant

### AWS / GitHub / Python platform docs
- AWS API Gateway: REST vs HTTP APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html
- AWS API Gateway: protect REST APIs with AWS WAF
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html
- AWS API Gateway: disable default endpoint for REST APIs
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-disable-default-endpoint.html
- AWS API Gateway: Regional custom domain names
  https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-regional-api-custom-domain-create.html
- AWS API Gateway: API mappings for custom domains
  https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-mappings.html
- AWS API Gateway: integration types
  https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-integration-types.html
- AWS CDK CloudFront behavior defaults
  https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudfront/Behavior.html
- AWS WAF rate-based rules
  https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html
- AWS WAF logging
  https://docs.aws.amazon.com/waf/latest/developerguide/logging.html
- API Gateway logging
  https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html
- Lambda reserved concurrency
  https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html
- Lambda concurrency concepts
  https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html
- S3 abort incomplete multipart uploads
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html
- Step Functions retries and error handling
  https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html
- GitHub Actions OIDC in AWS
  https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- GitHub Actions reusable workflows
  https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows
- GitHub Actions artifact attestations
  https://docs.github.com/en/actions/concepts/security/artifact-attestations
- OpenAI Codex MCP
  https://developers.openai.com/codex/mcp
- OpenAI Codex skills
  https://developers.openai.com/codex/skills/
- OpenAI Docs MCP
  https://developers.openai.com/learn/docs-mcp/
- uv locking and syncing
  https://docs.astral.sh/uv/concepts/projects/sync/
- uv workspaces
  https://docs.astral.sh/uv/concepts/projects/workspaces/
- pytest good practices / importlib mode
  https://docs.pytest.org/en/stable/explanation/goodpractices.html
- FastAPI CORS
  https://fastapi.tiangolo.com/tutorial/cors/
- FastAPI settings / Pydantic settings
  https://fastapi.tiangolo.com/advanced/settings/
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Google Python Style Guide
  https://google.github.io/styleguide/pyguide.html

### AWS / documentation MCP references
- AWS MCP Server user guide
  https://docs.aws.amazon.com/aws-mcp/latest/userguide/what-is-mcp-server.html
- AWS Documentation MCP Server
  https://awslabs.github.io/mcp/servers/aws-documentation-mcp-server
- AWS Knowledge MCP Server
  https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server

### Context7 / Exa
- Context7 GitHub / setup docs
  https://github.com/upstash/context7
- Exa search docs
  https://exa.ai/docs/reference/search-api-guide
  https://exa.ai/docs/reference/search-best-practices

### Upstream runtime examples to inspect only after official docs
- Mangum upstream
  https://github.com/Kludex/mangum
  https://mangum.fastapiexpert.com/
- AWS Lambda Web Adapter upstream
  https://github.com/awslabs/aws-lambda-web-adapter
