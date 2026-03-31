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
