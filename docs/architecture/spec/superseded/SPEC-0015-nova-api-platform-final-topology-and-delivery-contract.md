---
Spec: 0015
Title: Nova API platform final topology and delivery contract
Status: Superseded
Superseded-by: "[SPEC-0029: Platform serverless](../SPEC-0029-platform-serverless.md)"
Version: 2.0
Date: 2026-03-03
Related:
  - "[ADR-0015: Nova API platform final hosting and deployment architecture (2026)](../../adr/superseded/ADR-0015-nova-api-platform-final-hosting-and-deployment-architecture-2026.md)"
  - "[ADR-0023: Hard cut to a single canonical /v1 API surface](../../adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API Contract](./SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: Hard-cut v1 route contract and route-literal guardrails](../SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../../requirements.md)"
  - "[ADR-0024: Layered runtime authority pack for the Nova monorepo](../../adr/ADR-0024-layered-architecture-authority-pack.md)"
  - "[ADR-0031: Reusable GitHub workflow API and versioning policy for deployment automation](../../adr/ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md)"
  - "[ADR-0032: OIDC and IAM role partitioning for deploy automation](../../adr/ADR-0032-oidc-and-iam-role-partitioning-for-deploy-automation.md)"
  - "[SPEC-0024: CloudFormation module contract](../SPEC-0024-cloudformation-module-contract.md)"
  - "[SPEC-0025: Reusable workflow integration contract](../SPEC-0025-reusable-workflow-integration-contract.md)"
  - "[SPEC-0026: CI/CD IAM least-privilege matrix](../SPEC-0026-ci-cd-iam-least-privilege-matrix.md)"
  - "[SPEC-0021: Downstream hard-cut integration and consumer validation contract](../SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md)"
  - "[SPEC-0022: Auth0 tenant ops reusable workflow contract](../SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md)"
  - "[SPEC-0023: SSM runtime base-url contract for deploy validation](./SPEC-0023-ssm-runtime-base-url-contract-for-deploy-validation.md)"
  - "[SPEC-0003: Observability](../SPEC-0003-observability.md)"
  - "[SPEC-0004: CI/CD and documentation automation](../SPEC-0004-ci-cd-and-docs.md)"
  - "[SPEC-0008: Async jobs and worker orchestration](./SPEC-0008-async-jobs-and-worker-orchestration.md)"
---

> Historical traceability note: this ECS-era topology contract is preserved for
> lineage only. The active infrastructure/runtime topology is documented in
> `SPEC-0029`.

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

- Public edge: CloudFront distribution with CLOUDFRONT-scope WAF.
- Origin layer: internal ALB reached through a CloudFront VPC origin.
- API service: FastAPI on ECS/Fargate behind the internal ALB.
- Worker service(s): ECS/Fargate consuming SQS queues (with DLQ).
- Optional scheduler path: EventBridge Scheduler -> SQS -> worker.

### 3.2 Network/security

- Private subnets for ECS tasks and the ALB origin.
- CloudFront is the only public ingress path for the API service.
- ALB ingress is restricted to the CloudFront-managed prefix list, a pinned
  CIDR, or an explicit source security group.
- Least-privilege SGs and IAM task roles.
- Secrets in Secrets Manager with KMS encryption.
- Bearer JWT verification remains application-authoritative in Nova.

### 3.3 Reliability/rollback

- API deployment uses ECS-native blue/green with bake time and CloudWatch alarm
  rollback controls.
- Worker deployment uses ECS rolling deploys with deployment circuit breaker
  protection.
- Health endpoints are `/v1/health/live` and `/v1/health/ready`.

## 4. IaC ownership map (required)

Nova repo must own runtime-deployment IaC for:

1. ECS services/task definitions (API + workers).
2. CloudFront edge, CLOUDFRONT-scope WAF, ALB/listeners/target groups, and
   VPC-origin wiring.
3. Queue and DLQ resources + scaling policies.
4. Secrets/KMS policy modules.
5. Observability resources (dashboards/alarms/log groups).
6. Release promotion stack templates and public base-url SSM marker stacks.

## 5. CI/CD contract

Required workflows in `.github/workflows/`:

- `ci.yml`
- `release-plan.yml`
- `release-apply.yml`
- `publish-packages.yml`
- `promote-prod.yml`
- `deploy-dev.yml`
- `post-deploy-validate.yml`
- `reusable-release-plan.yml`
- `reusable-release-apply.yml`
- `reusable-bootstrap-foundation.yml`
- `reusable-deploy-runtime.yml`
- `reusable-post-deploy-validate.yml`
- `reusable-deploy-dev.yml`
- `reusable-promote-prod.yml`

`post-deploy-validate.yml` is the manual entrypoint wrapper.
`reusable-post-deploy-validate.yml` owns the shared `workflow_call` API used by
Nova and downstream consumer repositories.
Container image build and push authority lives in CodeBuild via
`buildspecs/buildspec-release.yml`, not a GitHub Actions image-wrapper
workflow.

`ci.yml` is the unified protected-branch workflow shell for runtime quality,
generated-client drift checks, and cross-language conformance lanes. CFN/docs
authority validation remains separate in `cfn-contract-validate.yml`.

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
