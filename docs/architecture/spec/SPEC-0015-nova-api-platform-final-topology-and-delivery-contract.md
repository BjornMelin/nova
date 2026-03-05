---
Spec: 0015
Title: Nova API platform final topology and delivery contract
Status: Active
Version: 2.0
Date: 2026-03-03
Related:
  - "[ADR-0015: Nova API platform final hosting and deployment architecture (2026)](../adr/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API Contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](./SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[ADR-0024: Native-CFN modular stack architecture for Nova infrastructure productization](../adr/ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0025: Reusable GitHub workflow API and versioning policy for deployment automation](../adr/ADR-0025-runtime-monorepo-component-boundaries-and-ownership.md)"
  - "[ADR-0026: OIDC and IAM role partitioning for deploy automation](../adr/ADR-0026-fail-fast-runtime-configuration-and-safe-auth-execution.md)"
  - "[SPEC-0017: CloudFormation module contract](./SPEC-0017-runtime-component-topology-and-ownership-contract.md)"
  - "[SPEC-0018: Reusable workflow integration contract](./SPEC-0018-runtime-configuration-and-startup-validation-contract.md)"
  - "[SPEC-0019: CI/CD IAM least-privilege matrix](./SPEC-0019-auth-execution-and-threadpool-safety-contract.md)"
  - "[SPEC-0020: Rollout and validation strategy](./SPEC-0020-architecture-authority-pack-and-documentation-synchronization-contract.md)"
  - "[SPEC-0021: Downstream hard-cut integration and consumer validation contract](./SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md)"
  - "[SPEC-0022: Auth0 tenant ops reusable workflow contract](./SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md)"
  - "[SPEC-0023: SSM runtime base-url contract for deploy validation](./SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md)"
  - "[SPEC-0003: Observability](./SPEC-0003-observability.md)"
  - "[SPEC-0004: CI/CD and documentation automation](./SPEC-0004-ci-cd-and-docs.md)"
  - "[SPEC-0008: Async jobs and worker orchestration](./SPEC-0008-async-jobs-and-worker-orchestration.md)"
---

## 1. Scope

Defines Nova runtime topology, IaC ownership, CI/CD artifacts, and the
canonical runtime API contract after hard cut.

Constraints:

1. Final-state only.
2. No compatibility shims/back-compat wrappers unless ADR-approved >=9.0.
3. Production-grade controls are mandatory in dev/prod with
   environment-appropriate sizing.

## 2. Route contract authority

Route-literal authority is owned by:

- `SPEC-0000` (HTTP contract semantics)
- `SPEC-0016` (canonical route set and guardrails)
- `ADR-0023` (hard-cut decision)

This spec does not restate route literals to avoid contract drift.

## 3. Final topology

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
- Health endpoints are `/v1/health/live` and `/v1/health/ready`.

## 4. IaC ownership map (required)

Nova repo must own runtime-deployment IaC for:

1. ECS services/task definitions (API + workers).
2. ALB/listeners/target groups/WAF association.
3. Queue and DLQ resources + scaling policies.
4. Secrets/KMS policy modules.
5. Observability resources (dashboards/alarms/log groups).
6. Release promotion stack templates.

## 5. CI/CD contract

Required workflows in `.github/workflows/`:

- `ci.yml`
- `release-plan.yml`
- `release-apply.yml`
- `publish-packages.yml`
- `promote-prod.yml`
- `build-and-publish-image.yml`
- `deploy-dev.yml`
- `post-deploy-validate.yml`
- `reusable-release-plan.yml`
- `reusable-release-apply.yml`
- `reusable-bootstrap-foundation.yml`
- `reusable-deploy-runtime.yml`
- `reusable-post-deploy-validate.yml`
- `reusable-deploy-dev.yml`
- `reusable-promote-prod.yml`
- `conformance-clients.yml`

`post-deploy-validate.yml` is the manual entrypoint wrapper.
`reusable-post-deploy-validate.yml` owns the shared `workflow_call` API used by
Nova and downstream consumer repositories.

`ci.yml` MUST enforce:

- canonical route literals and regex checks
- OpenAPI path policy (`/v1/*` + `/metrics/summary` only)
- runtime source bans for legacy route literals
- route decorator structure checks across runtime route-definition modules
  (including routers mounted via `include_router`)
- unique `operationId`

## 6. Canonical API capability coverage

Nova MUST preserve capability families defined in `SPEC-0000` and `SPEC-0016`:

- transfer orchestration
- async job control-plane operations
- internal worker result update path
- capability/release discovery
- health/readiness and operational metrics

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
6. Legacy route families are absent from runtime and OpenAPI.

## 10. Operational no-shim posture

No temporary compatibility adapters are allowed in runtime, API contract, or
deployment workflows unless a new ADR explicitly scores and approves the
exception.

## 11. Implementation plan reference

Execution blueprint:

- `docs/history/2026-03-v1-hard-cut/planning/2026-03-01-adr0015-spec0015-implementation-blueprint.md`
