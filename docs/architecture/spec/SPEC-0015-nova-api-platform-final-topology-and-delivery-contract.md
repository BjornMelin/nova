---
Spec: 0015
Title: Nova API platform final topology and delivery contract
Status: Planned
Version: 1.1
Date: 2026-03-02
Related:
  - "[ADR-0015: Nova API platform final hosting and deployment architecture (2026)](../adr/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md)"
  - "[SPEC-0000: HTTP API Contract (current baseline)](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0003: Observability (current baseline)](./SPEC-0003-observability.md)"
  - "[SPEC-0004: CI/CD and documentation automation (current baseline)](./SPEC-0004-ci-cd-and-docs.md)"
  - "[SPEC-0008: Async jobs and worker orchestration (current baseline)](./SPEC-0008-async-jobs-and-worker-orchestration.md)"
---

## 1. Scope

Defines Nova target-state runtime topology, IaC ownership, CI/CD artifacts, and
API capability contract for the next implementation branch.

This specification is intentionally ahead of current implementation and does not
replace current baseline operational behavior until target-state code is merged.

Constraints:
1. Final-state only.
2. No shims/back-compat wrappers unless separately ADR-approved >=9.0.
3. Production-grade controls are mandatory in dev/prod with
   environment-appropriate sizing.

## 2. State and supersession model

### 2.1 Current implemented baseline (still active)

Current operational behavior remains defined by:

- `SPEC-0000` for `/api/transfers/*` + `/api/jobs/*` routes
- `SPEC-0003` for `/healthz` + `/readyz` semantics
- `SPEC-0004` for current release workflow and quality gates
- `SPEC-0008` for async enqueue/result semantics

### 2.2 Target-state supersession trigger

This spec becomes active contract authority when target-state implementation
lands and docs are updated in the same PR. At that point:

- target `/v1/*` capability routes supersede current baseline routes as contract
  authority
- target workflow artifacts below become required operational CI/CD definitions

## 3. Final topology (target-state)

### 3.1 Core services

- API service: FastAPI on ECS/Fargate behind ALB.
- Worker service(s): ECS/Fargate consuming SQS queues (with DLQ).
- Optional scheduler path: EventBridge Scheduler -> SQS -> worker.

### 3.2 Network/security

- Private subnets for ECS tasks.
- ALB ingress policy by deployment mode (public/private).
- Least-privilege SGs and IAM task roles.
- Secrets in Secrets Manager with KMS encryption.
- WAF attached to public ALB.

### 3.3 Reliability/rollback

- Deployment circuit breaker and CloudWatch alarm rollback controls are
  mandatory.
- Health endpoints (`/v1/health/live`, `/v1/health/ready`) must remain
  lightweight and dependency-scoped.

## 4. IaC ownership map (required)

Nova repo must own runtime-deployment IaC for:
1. ECS services/task definitions (API + workers).
2. ALB/listeners/target groups/WAF association.
3. Queue and DLQ resources + scaling policies.
4. Secrets/KMS policy modules.
5. Observability resources (dashboards/alarms/log groups).
6. Release promotion stack templates.

## 5. CI/CD contract (target-state)

Required workflow artifacts to be added in the next feature branch:
- `ci.yml`: lint/type/test/security/contract checks.
- `build-and-publish-image.yml`: immutable ECR image digest output.
- `publish-packages.yml`: CodeArtifact publishing with validation gates.
- `deploy-dev.yml`: environment deploy and smoke validation.
- `promote-prod.yml`: manual approval + immutable digest promotion.
- `post-deploy-validate.yml`: runtime and endpoint conformance checks.
- `conformance-clients.yml`: Dash/Shiny/TS contract parity lane.

## 6. API platform capability contract (target-state)

Nova must expose abstraction endpoints sufficient for downstream clients:
- `/v1/jobs` (create/list/get/cancel/retry)
- `/v1/jobs/{id}/events` (poll/SSE)
- `/v1/capabilities`
- `/v1/resources/plan` (dry-run planning)
- `/v1/releases/info`
- `/v1/health/live`, `/v1/health/ready`

These endpoints are canonical for target state; client libraries consume these
instead of direct AWS primitives.

## 7. CodeArtifact release flow

Release stages:
1. Build/sign/package.
2. Publish to staged channel.
3. Validate installability, SBOM, vulnerability policy, provenance.
4. Promote to production channel.
5. Deploy runtime pinned to immutable versions.

Mandatory pre-publish gates:
- Contract tests pass.
- Security thresholds pass.
- Versioning policy pass.
- Reproducible build metadata present.

## 8. DX declaration contract

Client projects declare intent in `nova-project.yaml`:
- runtime profile and concurrency targets,
- async job/SLA profile,
- storage and secret requirements,
- observability and SLO needs.

Nova translates this declaration to infrastructure and enforces policy
centrally.

## 9. Acceptance criteria

1. Dev and prod both deploy through immutable artifact path.
2. Rollback drill evidence exists for current release train.
3. Dash/Shiny/TS conformance workflow green.
4. Cost controls exist (budgets/alarms, retention policies, scaling bounds).
5. No active runtime/deployment authority exists outside Nova repo.

## 10. Operational no-shim posture

No temporary compatibility adapters are allowed in runtime, API contract, or
deployment workflows unless a new ADR explicitly scores and approves the
exception.

## 11. Implementation plan reference

Execution blueprint (planning authority for implementation sequencing):
- `docs/plan/2026-03-01-adr0015-spec0015-implementation-blueprint.md`
