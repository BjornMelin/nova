# SUBPLAN-0003

- Branch name: `feat/subplan-0003-infra-cross-repo-integration`

Transition note (2026-03-02): This subplan is baseline historical execution
context. `container-craft` references here are migration evidence, not active
runtime/deployment authority.

## Infra + Cross-Repo Integration

Order: 3 of 5
Parent plan: `docs/plan/PLAN.md`
Depends on: `SUBPLAN-0001`, `SUBPLAN-0002`

## Persona

Cloud Platform Integration Engineer (AWS IaC + service contract alignment)

## Objective

Align runtime-to-infra contracts and validate AWS deployment wiring for sidecar
routing, SQS/Redis/DynamoDB dependencies, and operational guardrails.

## Scope

Repositories:

- `packages/nova_file_api`
- `packages/nova_auth_api`
- `packages/nova_file_api`
- `packages/nova_auth_api`
- `packages/nova_dash_bridge`
- `packages/contracts`
- `~/repos/work/infra-stack/container-craft`
- `~/repos/work/pca-analysis-dash/dash-pca` (config validation)

## Mandatory Research Inputs

- ECS LB health checks:
  <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/load-balancer-healthcheck.html>
- S3 Transfer Acceleration:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/transfer-acceleration.html>
- S3 multipart limits:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html>
- Presigned URL guardrails:
  <https://docs.aws.amazon.com/prescriptive-guidance/latest/presigned-url-best-practices/introduction.html>

## Checklist

### A. container-craft wiring

- [x] Validate and update `FILE_TRANSFER_*` env mapping consistency
- [x] Add/tune SQS/Redis/DynamoDB feature toggles
- [x] Align new queue retry env mappings:
  - `JOBS_SQS_RETRY_MODE`
  - `JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS`
- [ ] Validate sidecar ALB routing for `/api/transfers/*` and `/api/jobs/*`
- [ ] Tune health-check interval/threshold/start grace for ECS

### B. Security and IAM

- [x] Verify least-privilege IAM for S3/KMS/SQS/DynamoDB/Redis paths
- [x] Validate no public S3 access paths in deployment templates

### C. Deployment and config validation

- [ ] Validate non-prod deployment path end-to-end
- [x] Validate service config compatibility in `dash-pca`

## Acceptance Criteria

- Runtime and infra env contracts are aligned.
- Sidecar routing and health checks are validated in AWS deployment path.
- Dependency permissions and toggles are production-acceptable.

Live validation evidence should be recorded via:

- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
