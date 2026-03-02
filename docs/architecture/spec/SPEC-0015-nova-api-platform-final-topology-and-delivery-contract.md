---
Spec: 0015
Title: Nova API platform final topology and delivery contract
Status: Active
Version: 1.0
Date: 2026-03-01
Related:
  - "[ADR-0015: Nova API platform final hosting and deployment architecture (2026)](../adr/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md)"
  - "[SPEC-0000: HTTP API Contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0004: CI/CD and documentation automation](./SPEC-0004-ci-cd-and-docs.md)"
  - "[SPEC-0008: Async jobs and worker orchestration](./SPEC-0008-async-jobs-and-worker-orchestration.md)"
---

## 1. Scope

Defines Nova final-state runtime topology, IaC ownership map, CI/CD requirements, API capability contract for downstream clients (Dash/Shiny/TS), and CodeArtifact release gates.

Constraints:
1. Final-state only.
2. No shims/back-compat wrappers unless separately ADR-approved >=9.0.
3. Production-grade controls are mandatory in dev/prod with environment-appropriate sizing.

## 2. Final topology

### 2.1 Core services

- API service: FastAPI on ECS/Fargate behind ALB.
- Worker service(s): ECS/Fargate consuming SQS queues (with DLQ).
- Optional scheduler path: EventBridge Scheduler -> SQS -> worker.

### 2.2 Network/security

- Private subnets for ECS tasks.
- ALB ingress policy by deployment mode (public/private).
- Least-privilege SGs and IAM task roles.
- Secrets in Secrets Manager with KMS encryption.
- WAF attached to public ALB.

### 2.3 Reliability/rollback

- CodeDeploy ECS blue/green.
- Deployment circuit breaker and CloudWatch alarm rollback.
- Health endpoints (`/health/live`, `/health/ready`) must remain lightweight.

## 3. IaC ownership map (required)

Nova repo must own runtime-deployment IaC for:
1. ECS services/task definitions (API + workers).
2. ALB/listeners/target groups/WAF association.
3. CodeDeploy app/deployment groups.
4. Queue and DLQ resources + scaling policies.
5. Secrets/KMS policy modules.
6. Observability resources (dashboards/alarms/log groups).
7. Release promotion stack templates.

## 4. CI/CD contract

Required workflows:
- `ci.yml`: lint/type/test/security/contract checks.
- `build-and-publish-image.yml`: immutable ECR image digest output.
- `publish-packages.yml`: CodeArtifact publishing with validation gates.
- `deploy-dev.yml`: environment deploy and smoke validation.
- `promote-prod.yml`: manual approval + immutable digest promotion.
- `post-deploy-validate.yml`: runtime and endpoint conformance checks.
- `conformance-clients.yml`: Dash/Shiny/TS contract parity lane.

## 5. API platform capability contract

Nova must expose abstraction endpoints sufficient for downstream clients:
- `/v1/jobs` (create/list/get/cancel/retry)
- `/v1/jobs/{id}/events` (poll/SSE)
- `/v1/capabilities`
- `/v1/resources/plan` (dry-run planning)
- `/v1/releases/info`
- `/v1/health/live`, `/v1/health/ready`

These endpoints are canonical; client libraries consume these and not direct AWS primitives.

## 6. CodeArtifact release flow

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

## 7. DX declaration contract

Client projects declare intent in `nova-project.yaml`:
- runtime profile and concurrency targets,
- async job/SLA profile,
- storage and secret requirements,
- observability and SLO needs.

Nova translates this declaration to infrastructure and enforces policy centrally.

## 8. Acceptance criteria

1. Dev and prod both deploy through immutable artifact path.
2. Rollback drill evidence exists for current release train.
3. Dash/Shiny/TS conformance workflow green.
4. Cost controls exist (budgets/alarms, retention policies, scaling bounds).
5. No active runtime/deployment authority exists outside Nova repo.

## 9. Operational no-shim posture

No temporary compatibility adapters are allowed in runtime, API contract, or deployment workflows unless a new ADR explicitly scores and approves the exception.
