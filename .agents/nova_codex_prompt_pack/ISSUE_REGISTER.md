# Issue register used across all prompts

Use these stable issue IDs in every Codex session. Treat them as the required acceptance contract for the remediation program.

## [P0] Merge blockers

- **P0-1 — Runtime deployment ownership deleted without replacement.** Completed by Prompt 03. The repo now owns runtime deployment again through GitHub Actions reusable workflows, AWS OIDC, and immutable release-built runtime artifacts.
- **P0-2 — Current CloudFront API edge cannot serve write traffic.** Completed by Prompt 01. CloudFront was removed from the API path entirely, eliminating the write-method trap.
- **P0-3 — CloudFront/WAF is bypassable.** Completed by Prompt 01. The default `execute-api` endpoint is disabled and the custom domain is authoritative.

## [P1] High-severity design and operational defects

- **P1-1 — Browser/downstream integration has no coherent CORS model.** Completed by Prompt 02. FastAPI app CORS, infra allowed origins, and browser-contract tests now form one explicit contract.
- **P1-2 — Wrong AWS ingress product mix.** Completed by Prompt 01. The public ingress is now Regional REST API + direct Regional WAF + one canonical custom domain.
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
