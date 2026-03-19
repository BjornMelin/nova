# Decision Frameworks and Scores

> **Canonical option tables and narrative** for each decision now live in the pack ADRs under [`adr/`](adr/README.md). This file keeps **scoring rules**, **framework weight definitions**, the **promotion summary**, and pointers to rejected options so the audit methodology stays in one place without duplicating large matrices.

This document defines the custom weighted scoring systems used in the second-pass audit and indexes the scored options for each major decision.

## Scoring rules

- Every major decision is scored on a **1.0–10.0** scale.
- Only options scoring **9.0 or higher** are promoted into the final implementation program (with the **AWS composite** nuance documented in [ADR-0007](adr/ADR-0007-aws-target-platform.md)).
- Code/runtime and SDK matrices use **1–10 per criterion**.
- AWS matrices use **1–5 per criterion**, then normalize to a 10-point final score.

## Framework A — Code / runtime simplification

| Criterion | Weight |
| --- | --- |
| Native dependency leverage | 25 |
| Entropy / LOC / file reduction | 20 |
| Reliability / performance | 20 |
| Security / operability | 15 |
| DX / maintainability | 15 |
| Implementation tractability | 5 |

Interpretation:

- high scores favor dependency-native solutions, less custom code, and simpler steady-state maintenance
- a lower migration score can be tolerated when the long-term architecture win is large and breaking changes are allowed

**ADR index (Framework A):**

| Topic | ADR |
| --- | --- |
| Auth topology | [ADR-0001](adr/ADR-0001-single-runtime-auth-authority.md) |
| Public auth contract | [ADR-0002](adr/ADR-0002-bearer-jwt-public-auth-contract.md) |
| Worker result update path | [ADR-0003](adr/ADR-0003-worker-direct-result-persistence.md) |
| OpenAPI and operation-id strategy | [ADR-0004](adr/ADR-0004-native-fastapi-contract-expression.md) |
| Middleware and error strategy | [ADR-0009](adr/ADR-0009-shared-pure-asgi-middleware-and-errors.md) |
| Public Python surface and adapter strategy | [ADR-0005](adr/ADR-0005-async-first-public-surface.md) |

## Framework B — SDK strategy

| Criterion | Weight |
| --- | --- |
| Language ecosystem fit | 20 |
| Consumer ergonomics | 15 |
| Maintenance burden reduction | 25 |
| Type safety / correctness | 15 |
| Native tooling leverage | 15 |
| Migration clarity | 10 |

Interpretation:

- language-ecosystem fit matters because these SDKs must feel native to their consumers
- maintenance burden reduction is weighted heavily because current Nova spends too much code on SDK scaffolding

**ADR index (Framework B):** [ADR-0006 — SDK architecture by language](adr/ADR-0006-sdk-architecture-by-language.md) (TypeScript, Python, R subsections).

## Framework C — AWS architecture

| Criterion | Weight |
| --- | --- |
| Security / compliance | 5 |
| Reliability | 5 |
| Operability | 4 |
| Latency / user experience | 4 |
| Cost efficiency | 3 |
| Scalability / elasticity | 3 |
| Portability / lock-in | 2 |

Interpretation:

- this is the AWS-focused architecture matrix used to choose compute, front door, and datastore options
- it matches the recommended weighting pattern for serious AWS architecture reviews

**ADR index (Framework C):** [ADR-0007 — AWS target platform](adr/ADR-0007-aws-target-platform.md) (compute, front door, datastore, end-to-end tables).

## Final promoted decisions (all >= 9.0)

| Decision | Winning option | Score /10 | ADR |
| --- | --- | --- | --- |
| Auth topology | Inline async verifier in file API and delete auth service | 9.70 | [ADR-0001](adr/ADR-0001-single-runtime-auth-authority.md) |
| Public auth contract | Bearer JWT only; derive scope from claims | 9.35 | [ADR-0002](adr/ADR-0002-bearer-jwt-public-auth-contract.md) |
| Worker result update path | Direct service/repository updates from worker | 9.35 | [ADR-0003](adr/ADR-0003-worker-direct-result-persistence.md) |
| OpenAPI and operation-id strategy | Native FastAPI contract features with minimal hooks | 9.10 | [ADR-0004](adr/ADR-0004-native-fastapi-contract-expression.md) |
| Middleware and error strategy | Shared pure ASGI middleware + shared error registration | 9.15 | [ADR-0009](adr/ADR-0009-shared-pure-asgi-middleware-and-errors.md) |
| Public Python surface and adapter strategy | Async-first canonical surface + thin sync adapters | 9.35 | [ADR-0005](adr/ADR-0005-async-first-public-surface.md) |
| TypeScript SDK strategy | openapi-typescript + openapi-fetch | 9.50 | [ADR-0006](adr/ADR-0006-sdk-architecture-by-language.md) |
| Python SDK strategy | openapi-python-client with config + minimal templates | 9.10 | [ADR-0006](adr/ADR-0006-sdk-architecture-by-language.md) |
| R SDK strategy | Thin httr2 package with minimal metadata/codegen | 9.10 | [ADR-0006](adr/ADR-0006-sdk-architecture-by-language.md) |
| AWS datastore choice | DynamoDB | 9.31 | [ADR-0007](adr/ADR-0007-aws-target-platform.md) |
| End-to-end platform architecture | CloudFront + ALB + ECS/Fargate + S3/SQS/DynamoDB | 9.23 | [ADR-0007](adr/ADR-0007-aws-target-platform.md) |

## Repo rebaseline (program step)

The final branch **chore/repo-rebaseline-ci-release** is scored **9.17/10** in [manifest.json](manifest.json) as program prioritization. Narrative and commitments: [ADR-0008](adr/ADR-0008-repo-rebaseline-after-cuts.md).

## Not promoted into the final implementation program

Some options remain technically plausible but do **not** score above 9.0 under the green-field criteria. Those are documented in [`REJECTED_AND_DEFERRED_OPTIONS.md`](REJECTED_AND_DEFERRED_OPTIONS.md).

| Option | Native dependency leverage | Entropy / LOC / file reduction | Reliability / performance | Security / operability | DX / maintainability | Implementation tractability | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Keep same_origin + body/header session scope | 3 | 2 | 6 | 4 | 4 | 8 | 3.95 |
| Header-only session scope contract | 4 | 5 | 6 | 5 | 5 | 7 | 5.05 |
| Bearer JWT only; derive scope from claims | 10 | 9 | 9 | 10 | 9 | 8 | 9.35 |

**Winner:** `Bearer JWT only; derive scope from claims` — **9.35/10**

Deriving scope from verified claims is the cleanest and most secure design. Session/body scope inputs are a legacy surrogate that bloats every client and route.

## Worker result update path

Framework: **code_runtime**

| Option | Native dependency leverage | Entropy / LOC / file reduction | Reliability / performance | Security / operability | DX / maintainability | Implementation tractability | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Keep internal HTTP callback | 2 | 2 | 5 | 4 | 4 | 9 | 3.55 |
| Introduce async event fan-back for result updates | 5 | 4 | 8 | 7 | 6 | 5 | 5.85 |
| Direct service/repository updates from worker | 10 | 9 | 9 | 9 | 10 | 8 | 9.35 |

**Winner:** `Direct service/repository updates from worker` — **9.35/10**

Direct worker-side updates win because the current HTTP callback is an unnecessary self-hop that adds secrets, retries, latency, and failure modes without adding separation of concerns.

## OpenAPI and operation-id strategy

Framework: **code_runtime**

| Option | Native dependency leverage | Entropy / LOC / file reduction | Reliability / performance | Security / operability | DX / maintainability | Implementation tractability | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Keep bespoke schema surgery and path/method registries | 3 | 2 | 6 | 6 | 3 | 8 | 4.10 |
| Native FastAPI contract features with minimal hooks | 10 | 8 | 9 | 9 | 10 | 7 | 9.10 |
| Hand-authored static OpenAPI | 4 | 5 | 5 | 7 | 4 | 4 | 4.85 |

**Winner:** `Native FastAPI contract features with minimal hooks` — **9.10/10**

Native FastAPI declarations win because they align the code with the framework and shrink the custom contract layer dramatically while keeping stable operation IDs possible.

## Middleware and error strategy

Framework: **code_runtime**

| Option | Native dependency leverage | Entropy / LOC / file reduction | Reliability / performance | Security / operability | DX / maintainability | Implementation tractability | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Service-local HTTP middleware duplication | 3 | 2 | 6 | 6 | 4 | 8 | 4.25 |
| Shared pure ASGI middleware + shared error registration | 10 | 8 | 9 | 9 | 10 | 8 | 9.15 |
| Per-route request context and manual error wrapping | 4 | 3 | 5 | 5 | 3 | 6 | 4.10 |

**Winner:** `Shared pure ASGI middleware + shared error registration` — **9.15/10**

Pure ASGI middleware wins because it centralizes request context correctly and avoids the edge cases and duplication of ad-hoc HTTP middleware glue.

## Public Python surface and adapter strategy

Framework: **code_runtime**

| Option | Native dependency leverage | Entropy / LOC / file reduction | Reliability / performance | Security / operability | DX / maintainability | Implementation tractability | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Keep sync façade over async core | 4 | 3 | 6 | 7 | 5 | 8 | 5.00 |
| Async-first canonical surface + thin sync adapters | 10 | 9 | 9 | 9 | 10 | 8 | 9.35 |
| Sync-first canonical surface | 3 | 4 | 4 | 6 | 5 | 7 | 4.35 |

**Winner:** `Async-first canonical surface + thin sync adapters` — **9.35/10**

Async-first wins because Nova's core is already async. The current sync façade only exists to support adapters that should instead sit at the edges.

## TypeScript SDK strategy

Framework: **sdk**

| Option | Language ecosystem fit | Consumer ergonomics | Maintenance burden reduction | Type safety / correctness | Native tooling leverage | Migration clarity | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Keep custom fetch runtime and bespoke generator logic | 5 | 7 | 2 | 7 | 3 | 8 | 4.85 |
| openapi-typescript + openapi-fetch | 10 | 9 | 10 | 9 | 10 | 8 | 9.50 |
| openapi-generator typescript-fetch | 7 | 7 | 6 | 7 | 6 | 6 | 6.50 |

**Winner:** `openapi-typescript + openapi-fetch` — **9.50/10**

The openapi-ts stack wins because it is now mature, small, and directly aligned with the ecosystem. Nova's custom TS runtime is pure maintenance tax.

## Python SDK strategy

Framework: **sdk**

| Option | Language ecosystem fit | Consumer ergonomics | Maintenance burden reduction | Type safety / correctness | Native tooling leverage | Migration clarity | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Keep openapi-python-client plus large patch script | 8 | 8 | 3 | 8 | 4 | 8 | 6.15 |
| openapi-python-client with config + minimal templates | 10 | 9 | 9 | 9 | 9 | 8 | 9.10 |
| openapi-generator python | 6 | 7 | 6 | 6 | 6 | 6 | 6.15 |

**Winner:** `openapi-python-client with config + minimal templates` — **9.10/10**

`openapi-python-client` remains the right generator, but only when Nova stops fighting it with a giant patch script.

## R SDK strategy

Framework: **sdk**

| Option | Language ecosystem fit | Consumer ergonomics | Maintenance burden reduction | Type safety / correctness | Native tooling leverage | Migration clarity | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Keep current bespoke generated runtime | 6 | 7 | 4 | 6 | 4 | 8 | 5.55 |
| OpenAPI Generator R beta client | 5 | 5 | 6 | 4 | 6 | 7 | 5.45 |
| Thin httr2 package with minimal metadata/codegen | 10 | 9 | 9 | 9 | 9 | 8 | 9.10 |

**Winner:** `Thin httr2 package with minimal metadata/codegen` — **9.10/10**

A thin `httr2` package wins because it matches the R ecosystem and avoids both Nova's current bespoke runtime and the upstream beta generator's feature gaps.

## AWS compute choice

Framework: **aws**

| Option | Security / compliance | Reliability | Operability | Latency / user experience | Cost efficiency | Scalability / elasticity | Portability / lock-in | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lambda | 4 | 4 | 5 | 3 | 5 | 5 | 3 | 8.31 |
| ECS / Fargate | 5 | 5 | 4 | 5 | 4 | 4 | 3 | 8.92 |
| App Runner | 4 | 4 | 5 | 4 | 4 | 4 | 2 | 8.00 |
| EKS | 5 | 5 | 2 | 4 | 3 | 5 | 5 | 8.31 |

**Winner:** `ECS / Fargate` — **8.92/10**

ECS/Fargate edges out the alternatives because Nova is not just a bursty API; it is a steady HTTP service plus a long-running worker that benefits from shared runtime semantics.

## AWS API front door

Framework: **aws**

| Option | Security / compliance | Reliability | Operability | Latency / user experience | Cost efficiency | Scalability / elasticity | Portability / lock-in | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALB | 5 | 5 | 4 | 5 | 4 | 4 | 3 | 8.92 |
| API Gateway HTTP API | 5 | 5 | 4 | 4 | 4 | 5 | 2 | 8.69 |
| API Gateway REST API | 5 | 5 | 3 | 3 | 2 | 5 | 2 | 7.62 |

**Winner:** `ALB` — **8.92/10**

ALB narrowly wins for the chosen ECS deployment model because it is the simplest direct fit. API Gateway HTTP API remains a good alternative for some workloads but is not the strongest overall fit here.

## AWS datastore choice

Framework: **aws**

| Option | Security / compliance | Reliability | Operability | Latency / user experience | Cost efficiency | Scalability / elasticity | Portability / lock-in | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DynamoDB | 5 | 5 | 5 | 5 | 4 | 5 | 2 | 9.31 |
| Aurora / RDS | 5 | 4 | 3 | 4 | 3 | 3 | 3 | 7.46 |
| Redis-only persistence | 4 | 3 | 3 | 5 | 3 | 3 | 2 | 6.85 |

**Winner:** `DynamoDB` — **9.31/10**

DynamoDB is the strongest operational fit for Nova's job/activity metadata: managed, scalable, and well-matched to keyed access patterns.

## End-to-end platform architecture

Framework: **aws**

| Option | Security / compliance | Reliability | Operability | Latency / user experience | Cost efficiency | Scalability / elasticity | Portability / lock-in | Final /10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CloudFront + ALB + ECS/Fargate + S3/SQS/DynamoDB | 5 | 5 | 5 | 5 | 4 | 4 | 3 | 9.23 |
| CloudFront + API Gateway HTTP API + Lambda + S3/SQS/DynamoDB | 5 | 4 | 5 | 3 | 5 | 5 | 2 | 8.54 |
| CloudFront + App Runner + S3/SQS/DynamoDB | 4 | 4 | 5 | 4 | 4 | 4 | 2 | 8.00 |
| CloudFront + ALB + EKS + S3/SQS/DynamoDB | 5 | 5 | 2 | 4 | 3 | 5 | 5 | 8.31 |

**Winner:** `CloudFront + ALB + ECS/Fargate + S3/SQS/DynamoDB` — **9.23/10**

CloudFront + ALB + ECS/Fargate + S3/SQS/DynamoDB is the cleanest combined fit for Nova's steady API, worker, and managed-service priorities.

## Final promoted decisions (all >= 9.0)

| Decision | Winning option | Score /10 |
| --- | --- | --- |
| Auth topology | Inline async verifier in file API and delete auth service | 9.70 |
| Public auth contract | Bearer JWT only; derive scope from claims | 9.35 |
| Worker result update path | Direct service/repository updates from worker | 9.35 |
| OpenAPI and operation-id strategy | Native FastAPI contract features with minimal hooks | 9.10 |
| Middleware and error strategy | Shared pure ASGI middleware + shared error registration | 9.15 |
| Public Python surface and adapter strategy | Async-first canonical surface + thin sync adapters | 9.35 |
| TypeScript SDK strategy | openapi-typescript + openapi-fetch | 9.50 |
| Python SDK strategy | openapi-python-client with config + minimal templates | 9.10 |
| R SDK strategy | Thin httr2 package with minimal metadata/codegen | 9.10 |
| AWS datastore choice | DynamoDB | 9.31 |
| End-to-end platform architecture | CloudFront + ALB + ECS/Fargate + S3/SQS/DynamoDB | 9.23 |

## Not promoted into the final implementation program

Some options remain technically plausible but do **not** score above 9.0 under the green-field criteria. Those are documented in `REJECTED_AND_DEFERRED_OPTIONS.md`.
