# Deploy Runtime CloudFormation Environments Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-24

## Purpose

Deploy Nova runtime infrastructure stacks in a reproducible order, then publish
the public CloudFront base URLs required by CI/CD pipeline stacks through the
canonical SSM marker stacks.

Canonical operator path:

- `scripts/release/deploy-runtime-cloudformation-environment.sh`
- `runtime-config-contract.generated.md`
- The script applies the same change-set-first sequence documented here and
  requires `RUNTIME_COST_MODE` (`standard|saver|paused`) to select runtime
  cost posture before applying related override defaults (`AssignPublicIp=DISABLED`,
  async queue wiring, and file-transfer service deployment).

## Scope

This guide covers runtime stacks under `infra/runtime/**` for `dev` and `prod`.
It must be executed before CI/CD stack deployment guidance in:
[`nova-cicd-end-to-end-deploy.md`](nova-cicd-end-to-end-deploy.md).

## Prerequisites

1. AWS CLI v2 authenticated to target account and region.
2. `jq` installed.
3. Repository checkout at `${NOVA_REPO_ROOT}`.
4. Permissions for CloudFormation create/update/execute + IAM pass role for
   ECS/CloudFormation roles + service permissions for ECS/ELB/S3/SQS/DynamoDB/KMS.
5. Route53 update authority for both the internal ALB hosted zone and the
   public service hosted zone used by the CloudFront edge URL.
6. `AWS_REGION` must be `us-east-1` because the CloudFront edge, CLOUDFRONT-scope
   WAF, and ACM viewer certificate are deployed there.

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
- `ALB_HOSTED_ZONE_NAME` (example `internal.example.com`, typically a private hosted zone for the internal ALB origin)
- `ALB_HOSTED_ZONE_ID` (optional Route53 hosted zone ID for internal ALB cert/DNS automation)
- `ALB_DNS_NAME` (example `api-dev.internal.example.com`, validated internal ALB origin DNS used by the ALB certificate and the CloudFront origin TLS handshake)
- `ALB_NAME`
- `ALB_SCHEME` (`internal` only, default `internal`)
- `ENABLE_ALB_ACCESS_LOGS` (`true` or `false`, default `false`)
- `ALB_LOG_BUCKET` (required only when `ENABLE_ALB_ACCESS_LOGS=true`)
- `ECS_CLUSTER_NAME`
- `SERVICE_NAME`
- `SERVICE_DNS` (example `api.dev.example.com`, the public CloudFront API hostname)
- `PUBLIC_HOSTED_ZONE_ID` (Route53 hosted zone ID for `SERVICE_DNS` certificate validation and CloudFront alias records; it must be in the same AWS account as the deployment account because CloudFormation-managed ACM DNS validation can only create validation records in a hosted zone owned by that account)
- `DOCKER_REPOSITORY_NAME`
- `IMAGE_DIGEST` (OCI digest, `sha256:...`)
- `ENV_VARS_JSON` (JSON object string used only for supported non-secret API
  runtime overrides; it is validated by the operator script against the
  generated runtime config contract and exploded into explicit ECS environment
  entries rather than passed through as `ENV_DICT`)
- `RUNTIME_COST_MODE` (`standard`, `saver`, or `paused`)
- `OWNER_TAG`
- `ALARM_ACTION_ARN`
- `ASSIGN_PUBLIC_IP` (`ENABLED` or `DISABLED`, default `DISABLED`)

CloudFront ingress contract for the canonical operator script:

Do not export `ALB_INGRESS_PREFIX_LIST_ID`, `ALB_INGRESS_CIDR`, or
`ALB_INGRESS_SOURCE_SG_ID` when using
`scripts/release/deploy-runtime-cloudformation-environment.sh`.
The script resolves the AWS-managed CloudFront origin-facing prefix list
`com.amazonaws.global.cloudfront.origin-facing` and passes that value as
`AlbIngressPrefixListId` when deploying the cluster stack.

Network model requirements:

- `ASSIGN_PUBLIC_IP=DISABLED`: use private subnets with the required VPC
  interface endpoints wherever possible (for example ECR, Logs, Secrets
  Manager, and `ssmmessages`), adding NAT only when a dependency cannot be
  satisfied privately.
- `ASSIGN_PUBLIC_IP=ENABLED`: use subnet/routing that supports direct outbound
  internet egress for task bootstrap.

## Reproducible Deployment Sequence

Deploy in this order for each environment:

1. `infra/runtime/kms.yml`
2. `infra/runtime/ecr.yml`
3. `infra/runtime/ecs/cluster.yml`
4. `infra/runtime/file_transfer/s3.yml`
5. `infra/runtime/file_transfer/async.yml`
6. `infra/runtime/ecs/service.yml`
7. `infra/runtime/edge/cloudfront.yml`
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
export ENV_VARS_JSON='{"OIDC_ISSUER":"https://issuer.example.com/","OIDC_AUDIENCE":"api://nova","OIDC_JWKS_URL":"https://issuer.example.com/.well-known/jwks.json","FILE_TRANSFER_MAX_UPLOAD_BYTES":"536870912000"}'
export RUNTIME_COST_MODE=standard

"${NOVA_REPO_ROOT}/scripts/release/deploy-runtime-cloudformation-environment.sh"
```

The script deploys:

1. `infra/runtime/kms.yml`
2. `infra/runtime/ecr.yml`
3. `infra/runtime/ecs/cluster.yml`
4. `infra/runtime/file_transfer/s3.yml`
5. `infra/runtime/file_transfer/async.yml`
6. `infra/runtime/ecs/service.yml`
7. `infra/runtime/edge/cloudfront.yml`
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

- The service stack no longer accepts `ENV_DICT` / `AUTH_APP_SECRET` legacy
  env-bundle wiring.
- The service stack now owns the repo-managed ECS task role directly. Do not
  provide `TASK_ROLE_ARN`.
- The deploy operator resolves the ECS infrastructure role from the Nova IAM
  control-plane stack. Do not provide `ECS_INFRASTRUCTURE_ROLE_ARN`.
- The repo-managed runtime task roles preserve the ECS Exec session-channel
  permissions required when `EnableExecuteCommand` remains enabled; do not
  work around Exec failures by reintroducing external task-role inputs.
- The script resolves `com.amazonaws.global.cloudfront.origin-facing` and
  applies it as the ALB ingress prefix list so CloudFront remains the only
  public ingress path for the API service.
- Generic execution-role secret overrides are retired. Do not provide
  `TASK_EXECUTION_SECRET_ARNS` or `TASK_EXECUTION_SSM_PARAMETER_ARNS`.
- Async queue URL/table names and cache secret injection are derived from stack
  outputs, not operator JSON.
- The public validation base URL is published from the CloudFront edge stack
  (`PublicBaseUrl`), not from the ECS service stack output.
- `ENV_VARS_JSON` only supports implemented non-secret API overrides; the
  script rejects unsupported keys, including `IDEMPOTENCY_MODE` and
  `IDEMPOTENCY_DYNAMODB_TABLE`. `IDEMPOTENCY_DYNAMODB_TABLE` is stack-derived:
  when `IDEMPOTENCY_ENABLED=true`, the deploy flow passes
  `IdempotencyTableName` and `FileTransferIdempotencyTableArn` to the service
  stack, and the task definition injects `IDEMPOTENCY_DYNAMODB_TABLE` into the
  API container environment.
- The supported override list is generated from the canonical runtime settings
  contract; do not hand-edit duplicate key lists in docs or scripts.
- Runtime env var names remain stable, but the generator now reads only
  explicit string `Settings.validation_alias` mappings from `config.py`; it
  does not use `alias` or implicit uppercase fallback.
- Canonical worker runtime inputs are `JOBS_*`; stale worker aliases are not
  valid deployment inputs.
- Missing `OIDC_ISSUER`, `OIDC_AUDIENCE`, or `OIDC_JWKS_URL` now reaches
  CloudFormation successfully but must still fail Nova readiness until the
  bearer-verification dependency is fully configured.
- Treat that readiness failure as the canonical enforcement point. The runtime
  config contract and startup/readiness specs, not CloudFormation parameter
  validation, define the final bearer-verifier OIDC completeness rule.
- Default large-upload posture is `FILE_TRANSFER_MAX_UPLOAD_BYTES=536_870_912_000`
  and `FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS=1800`.
- If `FILE_TRANSFER_USE_ACCELERATE_ENDPOINT=true`, the bucket must already have
  Transfer Acceleration enabled and the bucket name must contain no periods.
- In private subnets without NAT/public egress, ECS Exec additionally requires
  the underlying Systems Manager Session Manager connectivity prerequisites
  such as `ssmmessages` VPC endpoint reachability.

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

## Cluster Stack Ingress Source Contract (direct template usage)

The reusable `infra/runtime/ecs/cluster.yml` template still requires exactly
one of:

- `AlbIngressPrefixListId`
- `AlbIngressCidr`
- `AlbIngressSourceSecurityGroupId`

Use these lower-level parameters only when you are deploying the cluster stack
directly and intentionally bypassing the canonical operator script. The
canonical script does not expose `ALB_INGRESS_*` environment variables and
always supplies the CloudFront managed prefix list automatically.

Additional cluster controls:

- `LoadBalancerScheme` supports `internal` only.
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
- When `IDEMPOTENCY_ENABLED=true`, pass async-stack outputs
  `IdempotencyTableName` and `FileTransferIdempotencyTableArn` into the service
  stack; the task definition then injects `IDEMPOTENCY_DYNAMODB_TABLE` into the
  API container environment.

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
    ServiceHostedZoneId="${PUBLIC_HOSTED_ZONE_ID}" \
    ServiceDNS="${SERVICE_DNS}" \
    ListenerRulePriority="100" \
    AlarmArn="${ALARM_ACTION_ARN}" \
    Owner="${OWNER_TAG}" \
    IdempotencyTableName="${IDEMPOTENCY_TABLE_NAME}" \
    FileTransferIdempotencyTableArn="${IDEMPOTENCY_TABLE_ARN}"
```

## Capture Runtime Outputs for CI/CD

After successful edge deployment, record base URLs for pipeline validation from
the runtime edge stack:

```bash
DEV_BASE_URL="$(aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-dev-runtime-edge" \
  --query "Stacks[0].Outputs[?OutputKey=='PublicBaseUrl'].OutputValue | [0]" \
  --output text)"

PROD_BASE_URL="$(aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-prod-runtime-edge" \
  --query "Stacks[0].Outputs[?OutputKey=='PublicBaseUrl'].OutputValue | [0]" \
  --output text)"

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

- Route/API documentation authority:
  [`../release/README.md#canonical-documentation-authority-chain`](../release/README.md#canonical-documentation-authority-chain)
- CloudFormation Parameters:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html>
- CloudFormation Fn::ImportValue restrictions:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/intrinsic-function-reference-importvalue.html>
- CloudFormation best practices:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html>
- ECS infrastructure IAM role for load balancers:
  <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AmazonECSInfrastructureRolePolicyForLoadBalancers.html>
