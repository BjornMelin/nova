# Deploy Runtime CloudFormation Environments Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-06

## Purpose

Converge a Nova runtime environment to the final AWS module topology with one
canonical operator path. This guide is the authority for `dev` and `prod`
runtime deployment before CI/CD bootstrap and release promotion.

## Canonical Path

Use only:

```bash
./scripts/release/deploy-runtime-cloudformation-environment.sh
```

Do not hand-stitch `infra/runtime/**` stacks ad hoc for live convergence, and
do not treat `.github/workflows/reusable-deploy-runtime.yml` as a substitute
for first-time or fix-forward runtime convergence. The reusable workflow is a
CI orchestration surface; this operator script is the canonical environment
convergence path.

The script deploys exactly this module sequence for one environment:

1. `infra/runtime/kms.yml`
2. `infra/runtime/ecr.yml`
3. `infra/runtime/ecs/cluster.yml`
4. `infra/runtime/file_transfer/s3.yml`
5. `infra/runtime/file_transfer/async.yml`
6. `infra/runtime/file_transfer/cache.yml`
7. `infra/runtime/ecs/service.yml`
8. `infra/runtime/file_transfer/worker.yml`
9. `infra/runtime/observability/ecs-observability-baseline.yml`
10. `infra/nova/deploy/service-base-url-ssm.yml`

## Final-Release Runtime Guardrails

The canonical script enforces the AWS release posture that matches active
authority:

- `AssignPublicIp=DISABLED`
- `IdempotencyMode=shared_required`
- `FileTransferAsyncEnabled=true`
- `FileTransferCacheEnabled=true`
- deterministic rollback alarm names bound into the ECS service
- change-set-first CloudFormation execution for every stack
- base-url SSM marker update at `/nova/{env}/{service}/base-url`

Additional hard guardrails:

- Use private subnets with NAT or required interface/gateway endpoints. Do not
  switch Nova release tasks to public-IP mode to compensate for missing
  network prerequisites.
- Use a dedicated runtime file-transfer bucket. Do not reuse the CI artifact bucket as the file-transfer bucket.
- Public ALBs are allowed, but they must be protected by the runtime cluster
  WebACL path from `infra/runtime/ecs/cluster.yml`.
- Worker tasks intentionally remain `IDEMPOTENCY_MODE=local_only`; do not wire
  shared-cache idempotency into the worker definition.
- Worker stack deployment always requires
  `JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN`, even when `WORKER_DESIRED_COUNT=0`
  and `WORKER_MIN_TASK_COUNT=0`.
- Worker autoscaling uses queue-depth step scaling to bootstrap from zero,
  react to sustained backlog, handle surge load, and scale in on sustained
  emptiness. Queue age is retained as an operator alarm.

## Prerequisites

1. AWS CLI v2 authenticated to the target account and region.
2. `jq` installed.
3. Repository checkout available at `${NOVA_REPO_ROOT}`.
4. CloudFormation/IAM/ECS/ELB/S3/SQS/DynamoDB/KMS/Secrets Manager permissions
   for the target account.
5. A valid task role ARN for the API service.
6. A valid worker update token secret ARN for the queue worker callback path.

## Required Inputs

Export these values before running the script:

- `AWS_REGION`
- `PROJECT`
- `APPLICATION`
- `ENVIRONMENT`
- `NOVA_REPO_ROOT`
- `VPC_ID`
- `SUBNET_IDS`
- `ALB_NAME`
- `ALB_HOSTED_ZONE_NAME`
- `ALB_DNS_NAME`
- exactly one of:
  `ALB_INGRESS_PREFIX_LIST_ID`, `ALB_INGRESS_CIDR`,
  `ALB_INGRESS_SOURCE_SG_ID`
- `ECS_CLUSTER_NAME`
- `SERVICE_NAME`
- `SERVICE_DNS`
- `DOCKER_REPOSITORY_NAME`
- `DOCKER_IMAGE_TAG`
- `TASK_ROLE_ARN`
- `OWNER_TAG`
- `ALARM_ACTION_ARN`
- `FILE_TRANSFER_BUCKET_BASE_NAME`
- `FILE_TRANSFER_CORS_ALLOWED_ORIGINS`
- `JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN`

Commonly overridden optional inputs:

- `CONTROL_PLANE_PROJECT` (default `nova`)
- `CONTROL_PLANE_APPLICATION` (default `ci`)
- `ALB_SCHEME` (`internet-facing` by default)
- `ALB_HOSTED_ZONE_ID`
- `ENABLE_ALB_ACCESS_LOGS`
- `ALB_LOG_BUCKET`
- `KMS_ALIAS`
- `API_DESIRED_COUNT`
- `API_TASK_CPU`
- `API_TASK_MEMORY`
- `WORKER_SERVICE_NAME`
- `WORKER_DESIRED_COUNT`
- `WORKER_MIN_TASK_COUNT`
- `WORKER_MAX_TASK_COUNT`
- `WORKER_SCALE_OUT_QUEUE_DEPTH_TARGET`
- `WORKER_SCALE_OUT_QUEUE_AGE_SECONDS_TARGET`
- `OBSERVABILITY_MIN_TASK_COUNT`
- `OBSERVABILITY_MAX_TASK_COUNT`

The script derives the remaining runtime wiring from stack outputs, including:

- KMS key ID/ARN/alias
- file-transfer bucket name
- async queue/table/activity ARNs and queue URL
- cache URL secret ARN
- ALB full name
- blue target-group full name
- runtime base URL

## Canonical Invocation

Run once for `dev`, then once for `prod`.

Example:

```bash
export AWS_REGION="us-east-1"
export PROJECT="nova"
export APPLICATION="file-api"
export ENVIRONMENT="dev"
export NOVA_REPO_ROOT="${PWD}"
export VPC_ID="vpc-0123456789abcdef0"
export SUBNET_IDS="subnet-aaaa1111,subnet-bbbb2222"
export ALB_NAME="nova-fileapi-dev-alb-public"
export ALB_HOSTED_ZONE_NAME="bjornmelin.io"
export ALB_DNS_NAME="api-dev-nova.bjornmelin.io"
export ALB_INGRESS_CIDR="0.0.0.0/0"
export ECS_CLUSTER_NAME="nova-file-api-dev"
export SERVICE_NAME="nova-file-api-dev"
export SERVICE_DNS="api-dev-nova.bjornmelin.io"
export DOCKER_REPOSITORY_NAME="nova-file-api"
export DOCKER_IMAGE_TAG="sha-RELEASE_DIGEST"
export TASK_ROLE_ARN="arn:aws:iam::123456789012:role/nova-file-api-nova-file-api-dev-ecs-task-us-east-1"
export OWNER_TAG="nova-release"
export ALARM_ACTION_ARN="arn:aws:sns:us-east-1:123456789012:nova-alarms"
export FILE_TRANSFER_BUCKET_BASE_NAME="nova-file-api-dev-transfer"
export FILE_TRANSFER_CORS_ALLOWED_ORIGINS="https://dash-dev.example.com"
export JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN="arn:aws:secretsmanager:us-east-1:123456789012:secret:nova/dev/jobs-worker-token"

./scripts/release/deploy-runtime-cloudformation-environment.sh
```

## What the Script Enforces

The script performs these checks before any change-set execution:

- required environment inputs are present
- exactly one ALB ingress source is provided
- `ENVIRONMENT` is `dev` or `prod`
- `ALB_SCHEME` is valid
- the CI artifact bucket, if discoverable, is not reused as the runtime
  transfer bucket
- `ECS_INFRASTRUCTURE_ROLE_ARN` is either provided directly or resolved from
  `${CONTROL_PLANE_PROJECT}-${CONTROL_PLANE_APPLICATION}-nova-iam-roles`

During deployment, the script:

- creates a named change set per stack
- inspects CloudFormation validation events before execution
- skips empty change sets without failing the full run
- waits for each stack to finish before continuing
- publishes the canonical base URL for the service into the CI-controlled SSM
  parameter stack

## Verification

Run after each environment convergence:

```bash
aws cloudformation list-stacks \
  --region "${AWS_REGION}" \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE

aws ecs describe-services \
  --region "${AWS_REGION}" \
  --cluster "${ECS_CLUSTER_NAME}" \
  --services "${PROJECT}-${APPLICATION}-${SERVICE_NAME}" \
  --query 'services[0].{deploymentController:deploymentController.type,strategy:deploymentConfiguration.strategy,assignPublicIp:networkConfiguration.awsvpcConfiguration.assignPublicIp}'

aws ssm get-parameter \
  --region "${AWS_REGION}" \
  --name "/nova/${ENVIRONMENT}/${SERVICE_NAME}/base-url"
```

Expected release posture:

- `deploymentController.type = ECS`
- `deploymentConfiguration.strategy = BLUE_GREEN`
- `assignPublicIp = DISABLED`
- runtime stack inventory includes `kms`, `ecr`, `cluster`, `s3`, `async`,
  `cache`, `service`, `worker`, and `observability`

## Relationship to CI/CD Bootstrap

This runtime convergence guide must be completed for both `dev` and `prod`
before:

- [day-0-operator-checklist.md](day-0-operator-checklist.md)
- [deploy-nova-cicd-end-to-end-guide.md](deploy-nova-cicd-end-to-end-guide.md)
- [release-promotion-dev-to-prod-guide.md](release-promotion-dev-to-prod-guide.md)

The CI/CD command pack depends on the SSM base-url markers this script writes.

## AWS References

- CloudFormation pre-deployment validation:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/validate-stack-deployments.html>
- Amazon ECS infrastructure IAM role for load balancers:
  <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AmazonECSInfrastructureRolePolicyForLoadBalancers.html>
- ECS deployment alarms:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ecs-service-deploymentalarms.html>
- ECS blue/green deployment workflow:
  <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/blue-green-deployment-how-it-works.html>
