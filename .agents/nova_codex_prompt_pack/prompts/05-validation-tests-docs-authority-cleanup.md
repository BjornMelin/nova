# Prompt 05 — Rebuild validation truth, expand tests to production reality, rewrite docs authority, and finish hard-cut cleanup

You are working inside the Nova repository. This is the **truth-restoration session**. Its job is to make the repo’s tests, docs, contracts, and validation mechanisms describe the system that now actually exists.

> Status: Completed on 2026-03-30
>
> Directly closed issue IDs: `P1-5`, `P2-1` (remaining runtime-truth half), `P2-4`, `P3-1`
>
> Prompt-05 completion summary:
> - Replaced shallow route-ping validation with deploy-output-bound runtime validation that now proves public release identity, readiness/liveness, protected-route auth rejection, CORS preflight behavior, and disabled `execute-api` ingress.
> - Expanded contract/test coverage so infra gates fail on drift in deploy-output authority, workflow APIs, docs routers, ingress truth, and generated runtime-config artifacts.
> - Rewrote active docs/router authority so the top-level doc chain points at the implemented wave-2 serverless baseline, deploy-output authority, and surviving release/runbook surfaces.
> - Removed deleted template-era runtime-config contract surfaces and kept only living deploy inputs plus API Lambda / workflow-task Lambda environment contracts.
>
> Prompt-05 verification summary:
> - `uv sync --locked --all-extras --dev` — passed
> - `uv run ruff check --fix` — passed
> - `uv run ruff format` — passed
> - `uv run ruff check` — passed
> - `uv run mypy .` — passed
> - `uv run pytest tests/infra -q` — passed (`84 passed`)
> - `uv run pytest packages/nova_file_api/tests -q` — passed (`153 passed`)
> - Read-only AWS verification in `us-east-1` confirmed the live dev stack still matches the intended Regional REST API + direct WAF + custom-domain authority, with access/WAF logs and S3 lifecycle cleanup active.
> - Approved closeout verification rebuilt a fresh deploy-output artifact from the live `NovaRuntimeStack` and ran `scripts/release/validate_runtime_release.py` successfully against the current dev runtime. The resulting report proved `/v1/releases/info`, `/v1/health/live`, `/v1/health/ready`, protected-route auth rejection, CORS preflight, disabled `execute-api`, and legacy-route `404` behavior.
>
> Prompt-05 residual note:
> - No redeploy was performed from this completion branch. Repo state and live runtime truth are now aligned for Prompt 05 validation concerns, but the updated GitHub workflow definitions themselves become live only after the branch carrying this patch set is merged and used for the next `Deploy Runtime` / `Post Deploy Validate` runs.

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

## There are no meaningful [P4] findings in the current review

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

- [x] **P1-5:** active docs/specs/runbooks/contracts are internally consistent.
- [x] **P2-1:** runtime validation proves the right deployed runtime, not just route reachability.
- [x] **P2-4:** tests assert production truth across ingress, provenance, logging, throttling, IAM, lifecycle, and docs authority.
- [x] **P3-1:** dead contract generators, aliases, and stale docs are removed or regenerated.
- [x] Consumer docs stop treating a manually configured base URL as the source of runtime authority.

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
  <https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html>
- AWS API Gateway: protect REST APIs with AWS WAF
  <https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html>
- AWS API Gateway: disable default endpoint for REST APIs
  <https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-disable-default-endpoint.html>
- AWS API Gateway: Regional custom domain names
  <https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-regional-api-custom-domain-create.html>
- AWS API Gateway: API mappings for custom domains
  <https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-mappings.html>
- AWS API Gateway: integration types
  <https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-integration-types.html>
- AWS CDK CloudFront behavior defaults
  <https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudfront/Behavior.html>
- AWS WAF rate-based rules
  <https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html>
- AWS WAF logging
  <https://docs.aws.amazon.com/waf/latest/developerguide/logging.html>
- API Gateway logging
  <https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html>
- Lambda reserved concurrency
  <https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html>
- Lambda concurrency concepts
  <https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html>
- S3 abort incomplete multipart uploads
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html>
- Step Functions retries and error handling
  <https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html>
- GitHub Actions OIDC in AWS
  <https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws>
- GitHub Actions reusable workflows
  <https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows>
- GitHub Actions artifact attestations
  <https://docs.github.com/en/actions/concepts/security/artifact-attestations>
- OpenAI Codex MCP
  <https://developers.openai.com/codex/mcp>
- OpenAI Codex skills
  <https://developers.openai.com/codex/skills/>
- OpenAI Docs MCP
  <https://developers.openai.com/learn/docs-mcp/>
- uv locking and syncing
  <https://docs.astral.sh/uv/concepts/projects/sync/>
- uv workspaces
  <https://docs.astral.sh/uv/concepts/projects/workspaces/>
- pytest good practices / importlib mode
  <https://docs.pytest.org/en/stable/explanation/goodpractices.html>
- FastAPI CORS
  <https://fastapi.tiangolo.com/tutorial/cors/>
- FastAPI settings / Pydantic settings
  <https://fastapi.tiangolo.com/advanced/settings/>
  <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>
- Google Python Style Guide
  <https://google.github.io/styleguide/pyguide.html>

### AWS / documentation MCP references

- AWS MCP Server user guide
  <https://docs.aws.amazon.com/aws-mcp/latest/userguide/what-is-mcp-server.html>
- AWS Documentation MCP Server
  <https://awslabs.github.io/mcp/servers/aws-documentation-mcp-server>
- AWS Knowledge MCP Server
  <https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server>

### Context7 / Exa

- Context7 GitHub / setup docs
  <https://github.com/upstash/context7>
- Exa search docs
  <https://exa.ai/docs/reference/search-api-guide>
  <https://exa.ai/docs/reference/search-best-practices>

### Upstream runtime examples to inspect only after official docs

- Mangum upstream
  <https://github.com/Kludex/mangum>
  <https://mangum.fastapiexpert.com/>
- AWS Lambda Web Adapter upstream
  <https://github.com/awslabs/aws-lambda-web-adapter>
