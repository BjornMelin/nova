# Risk Register and Mitigations

| Risk | Where it appears | Mitigation |
| --- | --- | --- |
| Hidden auth-service references remain after deletion | Branch 1 | grep workspaces, CI, Dockerfiles, docs, contracts, release scripts, and manifests; make deletion part of Definition of Done |
| Public consumers still depend on `session_id` contract | Branch 2 | major-version release notes, SDK regeneration, explicit docs/examples, no compatibility shim |
| Direct worker updates accidentally bypass metrics/activity logic | Branch 3 | extract or reuse a shared mutation primitive and cover it with tests |
| Native FastAPI contract rewrite changes operation IDs unexpectedly | Branch 4 | preserve explicit generation rule and run client/conformance checks |
| Middleware consolidation breaks streaming or request-id propagation | Branch 5 | use pure ASGI implementation and integration tests |
| Async-first surface regresses sync consumers | Branch 6 | keep thin sync adapters only where required and test them explicitly |
| TS SDK runtime migration changes consumer ergonomics unexpectedly | Branch 7 | provide a tiny `createNovaClient()` wrapper with auth/base-url convenience |
| Python generator simplification misses a necessary custom behavior | Branch 8 | classify every patch in the existing script before deleting it; preserve only justified behavior |
| R client rewrite loses ergonomic helpers used by Shiny apps | Branch 9 | validate package design against concrete Shiny-friendly usage flows before finalizing |
| Infra cleanup removes a deploy-time requirement that the auth service used to hide | Branch 10 | compare old/new environment contracts and update runbooks/alarms explicitly |
| Repo rebaseline leaves stale docs or CI references | Branch 11 | do a repo-wide stale-reference grep and use the review gate template rigorously |

## Principle

The right mitigation is usually:
- explicit deletion checks
- explicit contract tests
- explicit doc regeneration
- explicit review gates

not preserving legacy paths indefinitely.
