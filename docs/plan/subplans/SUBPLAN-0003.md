# SUBPLAN-0003

- Branch name: `feat/subplan-0003-infra-cross-repo-integration`

## Infra + Cross-Repo Integration

Order: 3 of 4
Parent plan: `docs/plan/PLAN.md`
Depends on: `SUBPLAN-0001`, `SUBPLAN-0002`

## Persona

Cloud Platform Integration Engineer (AWS IaC + service contract alignment)

## Objective

Align runtime-to-infra contracts and validate AWS deployment wiring for sidecar
routing, SQS/Redis/DynamoDB dependencies, and operational guardrails.

## Scope

Repositories:

- `~/repos/work/infra-stack/container-craft`
- `~/repos/work/infra-stack/aws-file-transfer-api`
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

- [ ] Validate and update `FILE_TRANSFER_*` env mapping consistency
- [ ] Add/tune SQS/Redis/DynamoDB feature toggles
- [ ] Validate sidecar ALB routing for `/api/file-transfer/*`
- [ ] Tune health-check interval/threshold/start grace for ECS

### B. Security and IAM

- [ ] Verify least-privilege IAM for S3/KMS/SQS/DynamoDB/Redis paths
- [ ] Validate no public S3 access paths in deployment templates

### C. Deployment and config validation

- [ ] Validate non-prod deployment path end-to-end
- [ ] Validate service config compatibility in `dash-pca`

## Acceptance Criteria

- Runtime and infra env contracts are aligned.
- Sidecar routing and health checks are validated in AWS deployment path.
- Dependency permissions and toggles are production-acceptable.
