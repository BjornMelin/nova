---
Spec: 0029
Title: Canonical serverless platform
Status: Active
Version: 1.0
Date: 2026-03-25
Supersedes: "[SPEC-0029: SDK architecture and artifact contract (superseded)](./superseded/SPEC-0029-sdk-architecture-and-artifact-contract.md)"
Related:
  - "[requirements-wave-2.md](../requirements-wave-2.md)"
  - "[ADR-0033: Canonical serverless platform](../adr/ADR-0033-canonical-serverless-platform.md)"
  - "[ADR-0036: DynamoDB idempotency and transient state, no Redis](../adr/ADR-0036-dynamodb-idempotency-no-redis.md)"
  - "[RUNBOOK-SERVERLESS-OPERATIONS.md](../../runbooks/RUNBOOK-SERVERLESS-OPERATIONS.md)"
References:
  - "[Canonical target state (2026-04)](../../overview/CANONICAL-TARGET-2026-04.md)"
  - "[Breaking changes v2](../../contracts/BREAKING-CHANGES-V2.md)"
---

## 1. Purpose

Define the approved target-state runtime platform for Nova after the wave-2
hard cut.

## 2. Runtime topology

- CloudFront + WAF
- API Gateway HTTP API
- Lambda using FastAPI via Lambda Web Adapter
- Step Functions Standard
- DynamoDB
- S3
- CloudWatch plus tracing/telemetry

## 3. IaC requirements

- the canonical infrastructure code lives in `infra/nova_cdk`
- the CDK app uses Python and models the API, workflow, storage, and
  observability surface as one coherent target platform

## 4. Network and security rules

- no public application subnets are required for the control plane
- use IAM roles and temporary credentials everywhere
- use Secrets Manager / Parameter Store for config and secrets
- use KMS encryption at rest
- use route-level JWT authorizers in API Gateway where they materially reduce
  noise before the app

## 5. Operational defaults

- reserved concurrency for blast-radius control
- provisioned concurrency only when justified by measured latency
- structured JSON logs
- correlation IDs across API and workflow boundaries
- RED metrics, saturation, and workflow failure metrics

## 6. Traceability

- [Architecture requirements](../requirements-wave-2.md#architecture-requirements)
- [Repo requirements](../requirements-wave-2.md#repo-requirements)
- [Quality requirements](../requirements-wave-2.md#quality-requirements)
