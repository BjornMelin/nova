# Decision matrices

> **Implementation state:** Decision frameworks used for the approved wave-2 architecture and repo simplification program.


All scores use custom weights specialized to Nova’s actual workload rather than the default generic template.

Scores are normalized to 10.0.

## 1) Compute + front door + workflow orchestration

### Requirements for this axis

- browser + client apps call a public API
- uploads/downloads are direct-to-S3 or URL-based, not proxied through the API
- async export processing must be durable and observable
- control-plane traffic is bursty
- the team benefits from lower ops and lower idle cost
- OpenAPI/client generation remains a first-class requirement

### Weights

| Criterion | Weight |
|---|---:|
| Reliability + durability | 5 |
| Operability | 5 |
| Cost efficiency | 5 |
| Burst elasticity | 4 |
| Workflow duration fit | 4 |
| API / OpenAPI fit | 4 |
| Service maturity | 4 |
| Latency / UX | 3 |

### Options

| Option | Weighted total | Score / 10 |
|---|---:|---:|
| API Gateway HTTP API + Lambda Web Adapter FastAPI + Step Functions Standard | 158 / 170 | 9.29 |
| ALB + ECS/Fargate + SQS worker | 141 / 170 | 8.29 |
| API Gateway HTTP API + Lambda durable functions | 136 / 170 | 8.00 |
| App Runner + SQS worker | 115 / 170 | 6.76 |

### Winner

**API Gateway HTTP API + Lambda Web Adapter FastAPI + Step Functions Standard**

Why it wins:

- lowest-ops control plane
- strong burst elasticity
- durable long-running orchestration without custom worker lifecycle plumbing
- cheaper idle posture than always-on ECS
- cleaner match for direct-to-S3 transfer control planes

## 2) Public auth model

### Weights

| Criterion | Weight |
|---|---:|
| Security / fail-closed behavior | 5 |
| Operational simplicity | 5 |
| Client clarity | 4 |
| OpenAPI correctness | 4 |
| Performance / latency | 3 |
| Green-field migration cleanliness | 2 |

### Options

| Option | Weighted total | Score / 10 |
|---|---:|---:|
| Bearer JWT only, verified in-process with async verifier, optional edge JWT authorizer | 111 / 115 | 9.65 |
| Dedicated remote auth service | 54 / 115 | 4.70 |
| Hybrid same-origin + remote/local JWT | 34 / 115 | 2.96 |

### Winner

**Bearer JWT only, verified in-process**

## 3) Async workflow contract model

### Weights

| Criterion | Weight |
|---|---:|
| Contract explicitness | 5 |
| DX / client ergonomics | 4 |
| Type safety | 4 |
| Operational simplicity | 4 |
| Future extensibility | 3 |
| Testability | 3 |

### Options

| Option | Weighted total | Score / 10 |
|---|---:|---:|
| Explicit export workflow resources and typed state transitions | 112 / 115 | 9.74 |
| Generic jobs with `job_type` + payload | 58 / 115 | 5.04 |
| Internal callback workflow lifecycle | 36 / 115 | 3.13 |

### Winner

**Explicit export workflow resources**

## 4) Idempotency + transient state persistence

### Weights

| Criterion | Weight |
|---|---:|
| Correctness under retries | 5 |
| Infra simplicity | 4 |
| Cost | 4 |
| Latency | 3 |
| Cross-instance consistency | 4 |
| Cognitive load | 3 |

### Options

| Option | Weighted total | Score / 10 |
|---|---:|---:|
| DynamoDB persistence with explicit expiration filtering and optional local hot cache | 107 / 115 | 9.30 |
| Redis + local TTL + DynamoDB hybrid | 73 / 115 | 6.35 |
| Redis only | 75 / 115 | 6.52 |

### Winner

**DynamoDB persistence with explicit expiration filtering**

## 5) TypeScript SDK generation

### Weights

| Criterion | Weight |
|---|---:|
| Generator maturity | 5 |
| Runtime maintenance burden | 5 |
| Client ergonomics | 4 |
| Type fidelity | 4 |
| Extensibility / plugin surface | 3 |

### Options

| Option | Weighted total | Score / 10 |
|---|---:|---:|
| `@hey-api/openapi-ts` generated SDKs | 100 / 105 | 9.52 |
| `openapi-typescript` + `openapi-fetch` + custom glue | 77 / 105 | 7.33 |
| Current bespoke `@nova/sdk-fetch` runtime | 49 / 105 | 4.67 |

### Winner

**`@hey-api/openapi-ts`**

## 6) Python SDK generation

### Weights

| Criterion | Weight |
|---|---:|
| Maintenance burden | 5 |
| Template control | 4 |
| Output typing quality | 4 |
| Ecosystem fit | 4 |
| Version maturity | 2 |

### Options

| Option | Weighted total | Score / 10 |
|---|---:|---:|
| `openapi-python-client` with minimal templates/config | 87 / 95 | 9.16 |
| OpenAPI Generator Python | 71 / 95 | 7.47 |
| Handwritten Python SDK | 55 / 95 | 5.79 |

### Winner

**`openapi-python-client` with much less customization**

## 7) R client strategy

### Weights

| Criterion | Weight |
|---|---:|
| Maintainability | 5 |
| Shiny / API ergonomics | 4 |
| Auth/fetch flexibility | 4 |
| Generation reliability | 4 |
| Package maturity | 4 |

### Options

| Option | Weighted total | Score / 10 |
|---|---:|---:|
| Thin `httr2` package | 101 / 105 | 9.61 |
| OpenAPI Generator R package | 46 / 105 | 4.38 |
| Handwritten base-R HTTP helpers | 57 / 105 | 5.43 |

### Winner

**Thin `httr2` package**

## 8) Docs authority model

### Weights

| Criterion | Weight |
|---|---:|
| Drift reduction | 5 |
| Contributor signal-to-noise | 5 |
| Test ROI | 4 |
| Auditability | 3 |
| Release safety | 3 |

### Options

| Option | Weighted total | Score / 10 |
|---|---:|---:|
| Canonical small active set + archive everything else | 94 / 100 | 9.40 |
| Keep current broad active docs authority surface | 41 / 100 | 4.10 |

### Winner

**Canonical small active set + archive everything else**
