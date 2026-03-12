# Deploy Runtime CloudFormation Environments Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-11

## Purpose

Deploy Nova runtime infrastructure stacks in a reproducible order for any AWS
account/region, then produce the environment base URLs required by CI/CD
pipeline stacks.

Canonical operator path:

- `scripts/release/deploy-runtime-cloudformation-environment.sh`
- The script applies the same change-set-first sequence documented here and
  requires `RUNTIME_COST_MODE` (`standard|saver|paused`) to select runtime
  cost posture before applying related override defaults (`AssignPublicIp=DISABLED`,
  `IDEMPOTENCY_MODE=shared_required`, async queue wiring, and cache-enabled
  file-transfer service deployment).

## Scope

This guide covers runtime stacks under `infra/runtime/**` for `dev` and `prod`.
It must be executed before CI/CD stack deployment guidance in:
`deploy-nova-cicd-end-to-end-guide.md`.

## Prerequisites

1. AWS CLI v2 authenticated to target account and region.
2. `jq` installed.
3. Repository checkout at `${NOVA_REPO_ROOT}`.
4. Permissions for CloudFormation create/update/execute + IAM pass role for
   ECS/CloudFormation roles + service permissions for ECS/ELB/S3/SQS/DynamoDB/KMS.
5. Hosted zone ownership or delegated DNS update authority when using ALB DNS.

## Required Inputs

Export these values before running commands:

- `AWS_REGION`
- `AWS_ACCOUNT_ID`
- `PROJECT` (default `nova`)
- `APPLICATION` (service family, for example `file-api`)
- `CONTROL_PLANE_PROJECT` (default `nova`, used for base-url SSM marker stacks)
- `CONTROL_PLANE_APPLICATION` (default `ci`, used for base-url SSM marker stacks)
- `ENVIRONMENT` (`dev` or `prod`)
- `NOVA_REPO_ROOT`
- `VPC_ID`
- `SUBNET_IDS` (comma-delimited subnet IDs used by ECS task ENIs)
- `ALB_HOSTED_ZONE_NAME` (example `internal.example.com`)
- `ALB_HOSTED_ZONE_ID` (optional Route53 hosted zone ID for cert DNS validation automation)
- `ALB_DNS_NAME` (example `api-dev.internal.example.com`)
- `ALB_NAME`
- `ALB_SCHEME` (`internal` or `internet-facing`, default `internal`)
- `ENABLE_ALB_ACCESS_LOGS` (`true` or `false`, default `false`)
- `ALB_LOG_BUCKET` (required only when `ENABLE_ALB_ACCESS_LOGS=true`)
- `ALB_INGRESS_PREFIX_LIST_ID` or `ALB_INGRESS_CIDR` or
  `ALB_INGRESS_SOURCE_SG_ID` (exactly one is required)
- `ECS_CLUSTER_NAME`
- `SERVICE_NAME`
- `SERVICE_DNS` (example `${SERVICE_NAME}.${ALB_HOSTED_ZONE_NAME}`)
- `DOCKER_REPOSITORY_NAME`
- `IMAGE_DIGEST` (OCI digest, `sha256:...`)
- `ENV_VARS_JSON` (JSON object string passed through `EnvVars`; it must include
  `IDEMPOTENCY_MODE=shared_required` and the async/cache runtime keys required
  by the current file-transfer service posture)
- `RUNTIME_COST_MODE` (`standard`, `saver`, or `paused`)
- `TASK_ROLE_ARN`
- `ECS_INFRASTRUCTURE_ROLE_ARN`
- `OWNER_TAG`
- `ALARM_ACTION_ARN`
- `ASSIGN_PUBLIC_IP` (`ENABLED` or `DISABLED`, default `DISABLED`)

Network model requirements:

- `ASSIGN_PUBLIC_IP=DISABLED`: use private subnets with NAT or required VPC
  interface endpoints (for ECR/API dependencies).
- `ASSIGN_PUBLIC_IP=ENABLED`: use subnet/routing that supports direct outbound
  internet egress for task bootstrap.

## Reproducible Deployment Sequence

Deploy in this order for each environment:

1. `infra/runtime/kms.yml`
2. `infra/runtime/ecr.yml`
3. `infra/runtime/ecs/cluster.yml`
4. `infra/runtime/file_transfer/s3.yml`
5. `infra/runtime/file_transfer/async.yml`
6. `infra/runtime/file_transfer/cache.yml` (optional)
7. `infra/runtime/ecs/service.yml`
8. `infra/runtime/file_transfer/worker.yml` (optional)
9. `infra/runtime/observability/ecs-observability-baseline.yml` (recommended)

Run the same sequence for `dev`, then `prod`, with environment-specific
parameters and names.

## Canonical Operator Script

Use the repository operator script when you want one audited path instead of
copying individual `aws cloudformation deploy` commands:

```bash
export ENVIRONMENT=dev
export IMAGE_DIGEST=sha256:...
export ENV_VARS_JSON='{"IDEMPOTENCY_MODE":"shared_required","JOBS_ENABLED":"true","JOBS_QUEUE_BACKEND":"sqs","JOBS_REPOSITORY_BACKEND":"dynamodb","JOBS_RUNTIME_MODE":"worker","CACHE_REDIS_URL":"rediss://..."}'
export JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN="arn:aws:secretsmanager:..."
export RUNTIME_COST_MODE=standard

"${NOVA_REPO_ROOT}/scripts/release/deploy-runtime-cloudformation-environment.sh"
```

The script deploys:

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

and preserves the documented change-set-first flow for each stack.

Runtime cost posture controls:

- `standard`: `API_TASK_CPU=2048`, `API_TASK_MEMORY=8192`,
  `API_DESIRED_COUNT=2`, `OBSERVABILITY_MIN_TASK_COUNT=2`
- `saver`: `API_TASK_CPU=512`, `API_TASK_MEMORY=1024`,
  `API_DESIRED_COUNT=1`, `OBSERVABILITY_MIN_TASK_COUNT=1`,
  `OBSERVABILITY_MAX_TASK_COUNT=2`
- `paused`: `API_DESIRED_COUNT=0`, `OBSERVABILITY_ENABLED=false`,
  `ENABLE_WORKER=false`

Worker/file-transfer contract notes:

- When `ENABLE_WORKER=true` and `FILE_TRANSFER_ASYNC_ENABLED=true`, the script
  now requires `JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN`.
- Canonical worker runtime inputs are `JOBS_*`; stale worker aliases are not
  valid deployment inputs.
- Default large-upload posture is `FILE_TRANSFER_MAX_UPLOAD_BYTES=536_870_912_000`
  and `FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS=1800`.
- If `FILE_TRANSFER_USE_ACCELERATE_ENDPOINT=true`, the bucket must already have
  Transfer Acceleration enabled and the bucket name must contain no periods.

## Change-Set-First Command Pattern

Use this pattern for every stack to keep deployments reproducible and auditable:

```bash
STACK_NAME="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-kms"
CHANGE_SET="${STACK_NAME}-cs-$(date +%Y%m%d%H%M%S)"

aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${STACK_NAME}" \
  --template-file "${NOVA_REPO_ROOT}/infra/runtime/kms.yml" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-execute-changeset \
  --change-set-name "${CHANGE_SET}" \
  --parameter-overrides \
    Project="${PROJECT}"

aws cloudformation describe-change-set \
  --region "${AWS_REGION}" \
  --stack-name "${STACK_NAME}" \
  --change-set-name "${CHANGE_SET}" \
  --query '{Status:Status,ExecutionStatus:ExecutionStatus,Reason:StatusReason,Changes:length(Changes)}'

aws cloudformation execute-change-set \
  --region "${AWS_REGION}" \
  --stack-name "${STACK_NAME}" \
  --change-set-name "${CHANGE_SET}"

aws cloudformation wait stack-update-complete \
  --region "${AWS_REGION}" \
  --stack-name "${STACK_NAME}" || \
aws cloudformation wait stack-create-complete \
  --region "${AWS_REGION}" \
  --stack-name "${STACK_NAME}"
```

## Cluster Stack Ingress Source Contract

`infra/runtime/ecs/cluster.yml` now requires exactly one of:

- `AlbIngressPrefixListId`
- `AlbIngressCidr`
- `AlbIngressSourceSecurityGroupId`

Additional cluster controls:

- `LoadBalancerScheme` supports `internal` or `internet-facing`.
- `HostedZoneId` is optional; when provided, ACM validation records can be
  provisioned automatically.
- `EnableLoadBalancerAccessLogs=true` requires `LoadBalancerLogBucket`.

Example using CIDR:

```bash
aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-cluster" \
  --template-file "${NOVA_REPO_ROOT}/infra/runtime/ecs/cluster.yml" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Project="${PROJECT}" \
    Application="${APPLICATION}" \
    EcsClusterName="${ECS_CLUSTER_NAME}" \
    LoadBalancerId="dash" \
    LoadBalancerName="${ALB_NAME}" \
    LoadBalancerScheme="${ALB_SCHEME}" \
    HostedZoneName="${ALB_HOSTED_ZONE_NAME}" \
    HostedZoneId="${ALB_HOSTED_ZONE_ID}" \
    LoadBalancerDNSName="${ALB_DNS_NAME}" \
    EnableLoadBalancerAccessLogs="${ENABLE_ALB_ACCESS_LOGS:-false}" \
    VpcId="${VPC_ID}" \
    SubnetList="${SUBNET_IDS}" \
    AlbIngressCidr="${ALB_INGRESS_CIDR}" \
    LoadBalancerLogBucket="${ALB_LOG_BUCKET}" \
    ImportKmsKeyId="${AWS_ACCOUNT_ID}:${AWS_REGION}:${PROJECT}:KmsKeyId"
```

## Service Stack Example

`infra/runtime/ecs/service.yml` contract notes:

- `AssignPublicIp` defaults to `DISABLED`; use `ENABLED` only when required by
  subnet/network architecture.
- If `FileTransferEnabled=true`, `FileTransferBucketName` must be provided.

```bash
aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-service" \
  --template-file "${NOVA_REPO_ROOT}/infra/runtime/ecs/service.yml" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Environment="${ENVIRONMENT}" \
    Project="${PROJECT}" \
    Application="${APPLICATION}" \
    Service="${SERVICE_NAME}" \
    EcsClusterName="${ECS_CLUSTER_NAME}" \
    LoadBalancerName="${ALB_NAME}" \
    DockerRepoName="${DOCKER_REPOSITORY_NAME}" \
    ImageDigest="${IMAGE_DIGEST}" \
    VpcId="${VPC_ID}" \
    SubnetList="${SUBNET_IDS}" \
    AssignPublicIp="${ASSIGN_PUBLIC_IP:-DISABLED}" \
    TaskRole="${TASK_ROLE_ARN}" \
    EcsInfrastructureRoleArn="${ECS_INFRASTRUCTURE_ROLE_ARN}" \
    ServiceDNS="${SERVICE_DNS}" \
    ListenerRulePriority="100" \
    AlarmArn="${ALARM_ACTION_ARN}" \
    Owner="${OWNER_TAG}"
```

## Capture Runtime Outputs for CI/CD

After successful service deployment, record base URLs for pipeline validation:

```bash
DEV_LOAD_BALANCER_DNS="$(aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-dev-runtime-cluster" \
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDnsName'].OutputValue | [0]" \
  --output text)"
DEV_BASE_URL="https://${DEV_LOAD_BALANCER_DNS}"

PROD_LOAD_BALANCER_DNS="$(aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-prod-runtime-cluster" \
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDnsName'].OutputValue | [0]" \
  --output text)"
PROD_BASE_URL="https://${PROD_LOAD_BALANCER_DNS}"

echo "DEV_BASE_URL=${DEV_BASE_URL}"
echo "PROD_BASE_URL=${PROD_BASE_URL}"
```

Persist these values to SSM for CI/CD authority:

Canonical stack ownership rule:

- Use only the CI control-plane stack pair to manage base-url parameters.
- Do not create additional stack names that manage the same parameter paths.

```bash
aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${CONTROL_PLANE_PROJECT:-nova}-${CONTROL_PLANE_APPLICATION:-ci}-dev-service-base-url" \
  --template-file "${NOVA_REPO_ROOT}/infra/nova/deploy/service-base-url-ssm.yml" \
  --parameter-overrides \
    Environment="dev" \
    ServiceName="${SERVICE_NAME}" \
    ServiceBaseUrl="${DEV_BASE_URL}"

aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${CONTROL_PLANE_PROJECT:-nova}-${CONTROL_PLANE_APPLICATION:-ci}-prod-service-base-url" \
  --template-file "${NOVA_REPO_ROOT}/infra/nova/deploy/service-base-url-ssm.yml" \
  --parameter-overrides \
    Environment="prod" \
    ServiceName="${SERVICE_NAME}" \
    ServiceBaseUrl="${PROD_BASE_URL}"
```

`scripts/release/day-0-operator-command-pack.sh` resolves these parameters from
`/nova/{env}/${SERVICE_NAME}/base-url` and fails fast on missing/invalid values.

## Verification

Run after each environment deployment:

```bash
aws ecs list-clusters --region "${AWS_REGION}"
aws elbv2 describe-load-balancers --region "${AWS_REGION}" --names "${ALB_NAME}"
aws cloudformation list-stacks --region "${AWS_REGION}" \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE
```

## References

- Requirements baseline (`requirements.md`):
  [../../architecture/requirements.md](../../architecture/requirements.md)
- ADR-0023 hard-cut canonical route surface:
  [../../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md](../../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md)
- SPEC-0000 HTTP API contract:
  [../../architecture/spec/SPEC-0000-http-api-contract.md](../../architecture/spec/SPEC-0000-http-api-contract.md)
- SPEC-0016 v1 route namespace and literal guardrails:
  [../../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md](../../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)
- CloudFormation Parameters:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html>
- CloudFormation Fn::ImportValue restrictions:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/intrinsic-function-reference-importvalue.html>
- CloudFormation best practices:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html>
- ECS infrastructure IAM role for load balancers:
  <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AmazonECSInfrastructureRolePolicyForLoadBalancers.html>
