# ADR-0033 -- Canonical serverless platform

> **Implementation state:** Implemented in the active canonical repository baseline.

## Status
Accepted

## Decision

Adopt **CloudFront + WAF → API Gateway HTTP API → Lambda (FastAPI via Lambda Web Adapter) → Step Functions Standard / DynamoDB / S3** as the canonical AWS runtime.

## Context

The active repository baseline uses the canonical serverless platform end to
end. Nova’s real workload is a direct-to-S3 transfer control plane with durable
async export processing, not a byte-streaming API.

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

- keep `infra/nova_cdk` as the canonical platform IaC surface
- keep `packages/nova_workflows` as the workflow/runtime implementation seam
- keep active docs, runbooks, and release flows aligned to the serverless/CDK surface only
