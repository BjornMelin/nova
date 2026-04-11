---
ADR: 0033
Title: Canonical serverless platform
Status: Implemented
Version: 1.1
Date: 2026-04-07
Related:
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[SPEC-0027: Public API v2](../spec/SPEC-0027-public-api-v2.md)"
  - "[SPEC-0028: Export workflow state machine](../spec/SPEC-0028-export-workflow-state-machine.md)"
  - "[SPEC-0029: Canonical serverless platform](../spec/SPEC-0029-platform-serverless.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[ADR-0034: Eliminate auth service and session auth](./ADR-0034-eliminate-auth-service-and-session-auth.md)"
  - "[ADR-0035: Replace generic jobs with export workflows](./ADR-0035-replace-generic-jobs-with-export-workflows.md)"
  - "[ADR-0036: DynamoDB idempotency and transient state, no Redis](./ADR-0036-dynamodb-idempotency-no-redis.md)"
  - "[ADR-0037: Consolidate SDK generation and package layout](./ADR-0037-sdk-generation-consolidation.md)"
  - "[ADR-0038: Reset docs authority](./ADR-0038-docs-authority-reset.md)"
  - "[ADR-0039: Explicit Lambda runtime bootstrap and typed runtime container](./ADR-0039-lambda-runtime-bootstrap-and-runtime-container.md)"
  - "[requirements.md](../requirements.md)"
---

## Decision

Adopt **regional API Gateway REST API + direct Regional WAF + one canonical
custom domain → Lambda (FastAPI via the repo-owned Lambda entrypoint,
Mangum-backed, zip-packaged, with an explicit process-reused `ApiRuntime`
container at `app.state.runtime`) → Step
Functions Standard / DynamoDB / S3** as the canonical AWS runtime, with the
default `execute-api` endpoint disabled.

## Context

The active repository baseline uses the canonical serverless platform end-to-
end. Nova's real workload is a direct-to-S3 transfer control plane with durable
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
- keep the public Lambda path on the explicit typed runtime bootstrap from
  `ADR-0039`; local development and tooling use the managed app builder
- keep public API packaging in release automation and have CDK consume explicit
  immutable artifact metadata instead of rebuilding the API package locally
- keep future transport additions native-first: use `StreamingResponse` for
  byte streaming, keep SSE on the documented FastAPI/Starlette integration path
  instead of a repo-local wrapper, and require explicit Lambda-fit
  justification before adding WebSocket or other long-lived connections
- keep `deploy-output.json` / `deploy-output.sha256` as the published runtime
  authority for the custom-domain base URL and deployed release provenance
- keep active docs, runbooks, and release flows aligned to the serverless/CDK surface only
