# ADR-0033 — Canonical serverless platform

> **Implementation state:** Approved target-state ADR. This decision is accepted for implementation but is not yet fully reflected in the current repository/runtime.


## Status
Accepted

## Decision

Adopt **CloudFront + WAF → API Gateway HTTP API → Lambda (FastAPI via Lambda Web Adapter) → Step Functions Standard / DynamoDB / S3** as the canonical AWS runtime.

## Context

The attached repo still centers ECS/Fargate, Redis, SQS, and a custom worker callback model. Nova’s real workload is a direct-to-S3 transfer control plane with durable async export processing, not a byte-streaming API.

## Why this wins

- lower idle cost than always-on ECS
- stronger fit for bursty control-plane workloads
- durable orchestration without custom worker callback complexity
- cleaner blast-radius control via Lambda concurrency and route-level authorizers
- easier decomposition into API vs orchestration responsibilities

## Rejected options

### ECS/Fargate + ALB + SQS worker
Good for steady traffic and long-lived services, but unnecessarily expensive and operationally heavy for Nova’s control-plane shape.

### Lambda durable functions
Promising, but still newer and narrower in maturity/region/runtime coverage than Step Functions Standard.

### App Runner
Operationally lighter than ECS, but weaker fit for the broader workflow/orchestration shape.

## Consequences

- add `infra/nova_cdk`
- add `packages/nova_workflows`
- remove the ECS/worker/Redis model from canonical docs and release flows
