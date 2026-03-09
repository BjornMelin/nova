#!/usr/bin/env bash
set -euo pipefail

# Canonical operator path for converging a Nova runtime environment to the
# final AWS module topology. Deploys the full runtime module set with a
# change-set-first flow, then updates the CI control-plane SSM base-url marker.

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

require_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required environment variable: $name" >&2
    exit 1
  fi
}

stack_exists() {
  local stack_name="$1"
  aws cloudformation describe-stacks \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" >/dev/null 2>&1
}

stack_output() {
  local stack_name="$1"
  local output_key="$2"
  aws cloudformation describe-stacks \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --query "Stacks[0].Outputs[?OutputKey==\`${output_key}\`].OutputValue | [0]" \
    --output text
}

describe_validation_events() {
  local stack_name="$1"
  local change_set_name="$2"
  aws cloudformation describe-events \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --change-set-name "$change_set_name" \
    --query "OperationEvents[?EventType=='VALIDATION_ERROR'].[ValidationName,ValidationStatus,ValidationFailureMode,ValidationPath,ValidationStatusReason]" \
    --output table || true
}

deploy_stack() {
  local stack_name="$1"
  local template_rel="$2"
  shift 2

  local template_file="${NOVA_REPO_ROOT}/${template_rel}"
  local change_set_name="${stack_name}-cs-$(date +%Y%m%d%H%M%S)"
  local existed="false"

  if [ ! -f "$template_file" ]; then
    echo "Missing template file: $template_file" >&2
    exit 1
  fi

  if stack_exists "$stack_name"; then
    existed="true"
  fi

  echo "==> ${stack_name}: create change set"
  aws cloudformation deploy \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --template-file "$template_file" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides "$@" \
    --change-set-name "$change_set_name" \
    --no-execute-changeset \
    --no-fail-on-empty-changeset >/dev/null

  aws cloudformation wait change-set-create-complete \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --change-set-name "$change_set_name" >/dev/null 2>&1 || true

  local status=""
  local reason=""
  status="$(aws cloudformation describe-change-set \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --change-set-name "$change_set_name" \
    --query 'Status' \
    --output text)"
  reason="$(aws cloudformation describe-change-set \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --change-set-name "$change_set_name" \
    --query 'StatusReason' \
    --output text)"

  if [ "$status" = "FAILED" ]; then
    if [[ "$reason" == *"didn't contain changes"* ]] || [[ "$reason" == *"No updates are to be performed"* ]]; then
      echo "==> ${stack_name}: no changes"
      return 0
    fi

    aws cloudformation describe-change-set \
      --region "$AWS_REGION" \
      --stack-name "$stack_name" \
      --change-set-name "$change_set_name" \
      --output json
    exit 1
  fi

  describe_validation_events "$stack_name" "$change_set_name"

  echo "==> ${stack_name}: execute change set"
  aws cloudformation execute-change-set \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --change-set-name "$change_set_name" >/dev/null

  if [ "$existed" = "true" ]; then
    aws cloudformation wait stack-update-complete \
      --region "$AWS_REGION" \
      --stack-name "$stack_name" >/dev/null
  else
    aws cloudformation wait stack-create-complete \
      --region "$AWS_REGION" \
      --stack-name "$stack_name" >/dev/null
  fi

  echo "==> ${stack_name}: complete"
}

require_exactly_one_ingress_source() {
  local count=0

  [ -n "${ALB_INGRESS_PREFIX_LIST_ID:-}" ] && count=$((count + 1))
  [ -n "${ALB_INGRESS_CIDR:-}" ] && count=$((count + 1))
  [ -n "${ALB_INGRESS_SOURCE_SG_ID:-}" ] && count=$((count + 1))

  if [ "$count" -ne 1 ]; then
    echo "Provide exactly one of ALB_INGRESS_PREFIX_LIST_ID, ALB_INGRESS_CIDR, or ALB_INGRESS_SOURCE_SG_ID." >&2
    exit 1
  fi
}

resolve_ecs_infrastructure_role() {
  if [ -n "${ECS_INFRASTRUCTURE_ROLE_ARN:-}" ]; then
    printf "%s" "$ECS_INFRASTRUCTURE_ROLE_ARN"
    return
  fi

  local stack_name="${CONTROL_PLANE_PROJECT}-${CONTROL_PLANE_APPLICATION}-nova-iam-roles"
  if stack_exists "$stack_name"; then
    local role_arn
    role_arn="$(stack_output "$stack_name" EcsInfrastructureRoleForLoadBalancersArn)"
    if [ -n "$role_arn" ] && [ "$role_arn" != "None" ]; then
      printf "%s" "$role_arn"
      return
    fi
    role_arn="$(stack_output "$stack_name" EcsInfrastructureRoleArn)"
    if [ -n "$role_arn" ] && [ "$role_arn" != "None" ]; then
      printf "%s" "$role_arn"
      return
    fi
  fi

  echo "Missing ECS_INFRASTRUCTURE_ROLE_ARN and no usable role output found in ${stack_name}." >&2
  exit 1
}

resolve_artifact_bucket_name() {
  if [ -n "${ARTIFACT_BUCKET_NAME:-}" ]; then
    printf "%s" "$ARTIFACT_BUCKET_NAME"
    return
  fi

  local stack_name="${CONTROL_PLANE_PROJECT}-${CONTROL_PLANE_APPLICATION}-nova-foundation"
  if stack_exists "$stack_name"; then
    local bucket_name
    bucket_name="$(stack_output "$stack_name" ArtifactBucketName)"
    if [ -n "$bucket_name" ] && [ "$bucket_name" != "None" ]; then
      printf "%s" "$bucket_name"
      return
    fi
  fi

  printf "%s" ""
}

require_cmd aws
require_cmd jq

AWS_REGION="${AWS_REGION:-us-east-1}"
CONTROL_PLANE_PROJECT="${CONTROL_PLANE_PROJECT:-nova}"
CONTROL_PLANE_APPLICATION="${CONTROL_PLANE_APPLICATION:-ci}"
ALB_SCHEME="${ALB_SCHEME:-internet-facing}"
ALB_LOAD_BALANCER_ID="${ALB_LOAD_BALANCER_ID:-dash}"
ENABLE_ALB_ACCESS_LOGS="${ENABLE_ALB_ACCESS_LOGS:-false}"
API_DESIRED_COUNT="${API_DESIRED_COUNT:-2}"
API_TASK_CPU="${API_TASK_CPU:-2048}"
API_TASK_MEMORY="${API_TASK_MEMORY:-8192}"
API_RUNTIME_PROFILE="${API_RUNTIME_PROFILE:-standard}"
API_LISTENER_RULE_PRIORITY="${API_LISTENER_RULE_PRIORITY:-100}"
WORKER_SERVICE_NAME="${WORKER_SERVICE_NAME:-${SERVICE_NAME:-}-worker}"
WORKER_DESIRED_COUNT="${WORKER_DESIRED_COUNT:-1}"
WORKER_MIN_TASK_COUNT="${WORKER_MIN_TASK_COUNT:-1}"
WORKER_MAX_TASK_COUNT="${WORKER_MAX_TASK_COUNT:-20}"
WORKER_TASK_CPU="${WORKER_TASK_CPU:-1024}"
WORKER_TASK_MEMORY="${WORKER_TASK_MEMORY:-2048}"
JOBS_REGION="${JOBS_REGION:-$AWS_REGION}"
JOBS_VISIBILITY_TIMEOUT_SECONDS="${JOBS_VISIBILITY_TIMEOUT_SECONDS:-120}"
JOBS_MESSAGE_RETENTION_SECONDS="${JOBS_MESSAGE_RETENTION_SECONDS:-345600}"
JOBS_MAX_RECEIVE_COUNT="${JOBS_MAX_RECEIVE_COUNT:-5}"
JOBS_SQS_MAX_NUMBER_OF_MESSAGES="${JOBS_SQS_MAX_NUMBER_OF_MESSAGES:-1}"
JOBS_SQS_WAIT_TIME_SECONDS="${JOBS_SQS_WAIT_TIME_SECONDS:-20}"
WORKER_SCALE_OUT_QUEUE_DEPTH_TARGET="${WORKER_SCALE_OUT_QUEUE_DEPTH_TARGET:-100}"
WORKER_SCALE_OUT_QUEUE_AGE_SECONDS_TARGET="${WORKER_SCALE_OUT_QUEUE_AGE_SECONDS_TARGET:-60}"
WORKER_SCALE_IN_COOLDOWN_SECONDS="${WORKER_SCALE_IN_COOLDOWN_SECONDS:-120}"
WORKER_SCALE_OUT_COOLDOWN_SECONDS="${WORKER_SCALE_OUT_COOLDOWN_SECONDS:-60}"
OBSERVABILITY_MIN_TASK_COUNT="${OBSERVABILITY_MIN_TASK_COUNT:-2}"
OBSERVABILITY_MAX_TASK_COUNT="${OBSERVABILITY_MAX_TASK_COUNT:-20}"
OBSERVABILITY_CPU_TARGET="${OBSERVABILITY_CPU_TARGET:-60}"
OBSERVABILITY_MEMORY_TARGET="${OBSERVABILITY_MEMORY_TARGET:-70}"
KMS_ALIAS="${KMS_ALIAS:-${PROJECT:-}-${APPLICATION:-}-${ENVIRONMENT:-}}"
FILE_TRANSFER_BUCKET_BASE_NAME="${FILE_TRANSFER_BUCKET_BASE_NAME:-}"
FILE_TRANSFER_CACHE_CLUSTER_NAME="${FILE_TRANSFER_CACHE_CLUSTER_NAME:-${PROJECT:-}-${APPLICATION:-}-${ENVIRONMENT:-}}"
FILE_TRANSFER_CACHE_URL_SECRET_NAME="${FILE_TRANSFER_CACHE_URL_SECRET_NAME:-/${PROJECT:-}/${APPLICATION:-}/${SERVICE_NAME:-}/${ENVIRONMENT:-}/file-transfer-cache}"
JOBS_QUEUE_NAME="${JOBS_QUEUE_NAME:-${PROJECT:-}-${APPLICATION:-}-${SERVICE_NAME:-}-${ENVIRONMENT:-}-jobs}"
JOBS_DEAD_LETTER_QUEUE_NAME="${JOBS_DEAD_LETTER_QUEUE_NAME:-${PROJECT:-}-${APPLICATION:-}-${SERVICE_NAME:-}-${ENVIRONMENT:-}-jobs-dlq}"
JOBS_TABLE_NAME="${JOBS_TABLE_NAME:-${PROJECT:-}-${APPLICATION:-}-${SERVICE_NAME:-}-${ENVIRONMENT:-}-jobs}"
ACTIVITY_TABLE_NAME="${ACTIVITY_TABLE_NAME:-${PROJECT:-}-${APPLICATION:-}-${SERVICE_NAME:-}-${ENVIRONMENT:-}-activity}"

require_env PROJECT
require_env APPLICATION
require_env ENVIRONMENT
require_env NOVA_REPO_ROOT
require_env VPC_ID
require_env SUBNET_IDS
require_env ALB_NAME
require_env ALB_HOSTED_ZONE_NAME
require_env ALB_DNS_NAME
require_env ECS_CLUSTER_NAME
require_env SERVICE_NAME
require_env SERVICE_DNS
require_env DOCKER_REPOSITORY_NAME
require_env DOCKER_IMAGE_TAG
require_env TASK_ROLE_ARN
require_env OWNER_TAG
require_env ALARM_ACTION_ARN
require_env FILE_TRANSFER_BUCKET_BASE_NAME
require_env FILE_TRANSFER_CORS_ALLOWED_ORIGINS
require_env JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN

if [ "$ENVIRONMENT" != "dev" ] && [ "$ENVIRONMENT" != "prod" ]; then
  echo "ENVIRONMENT must be dev or prod." >&2
  exit 1
fi

if [ "$ALB_SCHEME" != "internal" ] && [ "$ALB_SCHEME" != "internet-facing" ]; then
  echo "ALB_SCHEME must be internal or internet-facing." >&2
  exit 1
fi

if [ "$ENABLE_ALB_ACCESS_LOGS" = "true" ]; then
  require_env ALB_LOG_BUCKET
fi

require_exactly_one_ingress_source

ECS_INFRASTRUCTURE_ROLE_ARN="$(resolve_ecs_infrastructure_role)"
ARTIFACT_BUCKET_NAME="$(resolve_artifact_bucket_name)"

if [ "$WORKER_SERVICE_NAME" = "${SERVICE_NAME}" ]; then
  echo "WORKER_SERVICE_NAME must differ from SERVICE_NAME." >&2
  exit 1
fi

ROLLBACK_ALARM_PRIMARY="${PROJECT}-${APPLICATION}-${SERVICE_NAME}-${ENVIRONMENT}-api-latency-p95-rollback"
ROLLBACK_ALARM_SECONDARY="${PROJECT}-${APPLICATION}-${SERVICE_NAME}-${ENVIRONMENT}-api-5xx-rate-rollback"

KMS_STACK="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-kms"
ECR_STACK="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-ecr"
CLUSTER_STACK="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-cluster"
S3_STACK="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-s3"
ASYNC_STACK="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-async"
CACHE_STACK="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-cache"
SERVICE_STACK="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-service"
WORKER_STACK="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-worker"
OBSERVABILITY_STACK="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-observability"
BASE_URL_STACK="${CONTROL_PLANE_PROJECT}-${CONTROL_PLANE_APPLICATION}-${ENVIRONMENT}-service-base-url"

echo "==> Final release posture"
echo "Environment: ${ENVIRONMENT}"
echo "AssignPublicIp: DISABLED"
echo "IdempotencyMode: shared_required"
echo "FileTransferAsyncEnabled: true"
echo "FileTransferCacheEnabled: true"

deploy_stack \
  "$KMS_STACK" \
  "infra/runtime/kms.yml" \
  "Project=${PROJECT}" \
  "KmsAlias=${KMS_ALIAS}"

KMS_KEY_ID="$(stack_output "$KMS_STACK" KmsKeyId)"
KMS_KEY_ARN="$(stack_output "$KMS_STACK" KmsKeyArn)"
KMS_KEY_ALIAS="$(stack_output "$KMS_STACK" KmsKeyAlias)"

deploy_stack \
  "$ECR_STACK" \
  "infra/runtime/ecr.yml" \
  "Project=${PROJECT}" \
  "Application=${APPLICATION}" \
  "Service=${SERVICE_NAME}" \
  "EcrRepoName=${DOCKER_REPOSITORY_NAME}" \
  "EcrKmsAlias=${KMS_ALIAS}" \
  "UsedByEcs=true"

cluster_params=(
  "Project=${PROJECT}"
  "Application=${APPLICATION}"
  "EcsClusterName=${ECS_CLUSTER_NAME}"
  "LoadBalancerId=${ALB_LOAD_BALANCER_ID}"
  "LoadBalancerName=${ALB_NAME}"
  "LoadBalancerScheme=${ALB_SCHEME}"
  "HostedZoneName=${ALB_HOSTED_ZONE_NAME}"
  "LoadBalancerDNSName=${ALB_DNS_NAME}"
  "VpcId=${VPC_ID}"
  "SubnetList=${SUBNET_IDS}"
  "ListenerProtocol=https"
  "EnableLoadBalancerAccessLogs=${ENABLE_ALB_ACCESS_LOGS}"
  "ImportKmsKeyId=${KMS_KEY_ID}"
)

if [ -n "${ALB_HOSTED_ZONE_ID:-}" ]; then
  cluster_params+=("HostedZoneId=${ALB_HOSTED_ZONE_ID}")
fi
if [ "$ENABLE_ALB_ACCESS_LOGS" = "true" ]; then
  cluster_params+=("LoadBalancerLogBucket=${ALB_LOG_BUCKET}")
fi
if [ -n "${ALB_INGRESS_PREFIX_LIST_ID:-}" ]; then
  cluster_params+=("AlbIngressPrefixListId=${ALB_INGRESS_PREFIX_LIST_ID}")
fi
if [ -n "${ALB_INGRESS_CIDR:-}" ]; then
  cluster_params+=("AlbIngressCidr=${ALB_INGRESS_CIDR}")
fi
if [ -n "${ALB_INGRESS_SOURCE_SG_ID:-}" ]; then
  cluster_params+=("AlbIngressSourceSecurityGroupId=${ALB_INGRESS_SOURCE_SG_ID}")
fi

deploy_stack \
  "$CLUSTER_STACK" \
  "infra/runtime/ecs/cluster.yml" \
  "${cluster_params[@]}"

deploy_stack \
  "$S3_STACK" \
  "infra/runtime/file_transfer/s3.yml" \
  "Project=${PROJECT}" \
  "Application=${APPLICATION}" \
  "Service=${SERVICE_NAME}" \
  "Environment=${ENVIRONMENT}" \
  "BucketBaseName=${FILE_TRANSFER_BUCKET_BASE_NAME}" \
  "KmsAlias=${KMS_ALIAS}" \
  "CorsAllowedOrigins=${FILE_TRANSFER_CORS_ALLOWED_ORIGINS}"

FILE_TRANSFER_BUCKET_NAME="$(stack_output "$S3_STACK" BucketName)"
if [ -n "$ARTIFACT_BUCKET_NAME" ] && [ "$FILE_TRANSFER_BUCKET_NAME" = "$ARTIFACT_BUCKET_NAME" ]; then
  echo "Runtime file-transfer bucket must not reuse the CI artifact bucket (${ARTIFACT_BUCKET_NAME})." >&2
  exit 1
fi

deploy_stack \
  "$ASYNC_STACK" \
  "infra/runtime/file_transfer/async.yml" \
  "Project=${PROJECT}" \
  "Application=${APPLICATION}" \
  "Service=${SERVICE_NAME}" \
  "Environment=${ENVIRONMENT}" \
  "JobsQueueName=${JOBS_QUEUE_NAME}" \
  "JobsDeadLetterQueueName=${JOBS_DEAD_LETTER_QUEUE_NAME}" \
  "JobsTableName=${JOBS_TABLE_NAME}" \
  "ActivityTableName=${ACTIVITY_TABLE_NAME}" \
  "JobsVisibilityTimeoutSeconds=${JOBS_VISIBILITY_TIMEOUT_SECONDS}" \
  "JobsMessageRetentionSeconds=${JOBS_MESSAGE_RETENTION_SECONDS}" \
  "JobsMaxReceiveCount=${JOBS_MAX_RECEIVE_COUNT}" \
  "AlarmNotificationTopicArn=${ALARM_ACTION_ARN}"

JOBS_QUEUE_ARN="$(stack_output "$ASYNC_STACK" JobsQueueArn)"
JOBS_QUEUE_URL="$(stack_output "$ASYNC_STACK" JobsQueueUrl)"
JOBS_TABLE_ARN="$(stack_output "$ASYNC_STACK" JobsTableArn)"
ACTIVITY_TABLE_ARN="$(stack_output "$ASYNC_STACK" ActivityTableArn)"

deploy_stack \
  "$CACHE_STACK" \
  "infra/runtime/file_transfer/cache.yml" \
  "Project=${PROJECT}" \
  "Application=${APPLICATION}" \
  "Service=${SERVICE_NAME}" \
  "Environment=${ENVIRONMENT}" \
  "VpcId=${VPC_ID}" \
  "SubnetList=${SUBNET_IDS}" \
  "CacheClusterName=${FILE_TRANSFER_CACHE_CLUSTER_NAME}" \
  "CacheUrlSecretName=${FILE_TRANSFER_CACHE_URL_SECRET_NAME}"

CACHE_URL_SECRET_ARN="$(stack_output "$CACHE_STACK" CacheUrlSecretArn)"
CACHE_SECURITY_GROUP_EXPORT_NAME="${PROJECT}:${APPLICATION}:${SERVICE_NAME}:${ENVIRONMENT}:file-transfer-cache:sg-id"

deploy_stack \
  "$SERVICE_STACK" \
  "infra/runtime/ecs/service.yml" \
  "Environment=${ENVIRONMENT}" \
  "Project=${PROJECT}" \
  "Application=${APPLICATION}" \
  "Service=${SERVICE_NAME}" \
  "EcsClusterName=${ECS_CLUSTER_NAME}" \
  "LoadBalancerId=${ALB_LOAD_BALANCER_ID}" \
  "LoadBalancerName=${ALB_NAME}" \
  "DockerRepoName=${DOCKER_REPOSITORY_NAME}" \
  "DockerImageTag=${DOCKER_IMAGE_TAG}" \
  "TaskRole=${TASK_ROLE_ARN}" \
  "TaskCpu=${API_TASK_CPU}" \
  "TaskMemory=${API_TASK_MEMORY}" \
  "DesiredCount=${API_DESIRED_COUNT}" \
  "RuntimeProfile=${API_RUNTIME_PROFILE}" \
  "VpcId=${VPC_ID}" \
  "SubnetList=${SUBNET_IDS}" \
  "AssignPublicIp=DISABLED" \
  "ListenerRulePriority=${API_LISTENER_RULE_PRIORITY}" \
  "EcsInfrastructureRoleArn=${ECS_INFRASTRUCTURE_ROLE_ARN}" \
  "DeploymentRollbackAlarmNamePrimary=${ROLLBACK_ALARM_PRIMARY}" \
  "DeploymentRollbackAlarmNameSecondary=${ROLLBACK_ALARM_SECONDARY}" \
  "FileTransferEnabled=true" \
  "FileTransferBucketName=${FILE_TRANSFER_BUCKET_NAME}" \
  "FileTransferKmsAlias=${KMS_KEY_ALIAS}" \
  "FileTransferAsyncEnabled=true" \
  "FileTransferJobsQueueArn=${JOBS_QUEUE_ARN}" \
  "FileTransferJobsTableArn=${JOBS_TABLE_ARN}" \
  "FileTransferActivityTableArn=${ACTIVITY_TABLE_ARN}" \
  "FileTransferCacheEnabled=true" \
  "FileTransferCacheSecurityGroupExportName=${CACHE_SECURITY_GROUP_EXPORT_NAME}" \
  "FileTransferCacheUrlSecretArn=${CACHE_URL_SECRET_ARN}" \
  "IdempotencyMode=shared_required" \
  "TaskExecutionSecretArns=${CACHE_URL_SECRET_ARN}" \
  "ServiceDNS=${SERVICE_DNS}" \
  "Owner=${OWNER_TAG}"

BLUE_TARGET_GROUP_ARN="$(stack_output "$SERVICE_STACK" BlueTargetGroupArn)"
BLUE_TARGET_GROUP_FULL_NAME="$(aws elbv2 describe-target-groups \
  --region "$AWS_REGION" \
  --target-group-arns "$BLUE_TARGET_GROUP_ARN" \
  --query 'TargetGroups[0].TargetGroupFullName' \
  --output text)"
ALB_FULL_NAME="$(stack_output "$CLUSTER_STACK" LoadBalancerFullName)"
API_BASE_URL="$(stack_output "$SERVICE_STACK" EcsDnsName)"
API_ECS_SERVICE_NAME="${PROJECT}-${APPLICATION}-${SERVICE_NAME}"
SERVICE_LOG_GROUP_NAME="${PROJECT}-${APPLICATION}/${SERVICE_NAME}/ecs"

deploy_stack \
  "$WORKER_STACK" \
  "infra/runtime/file_transfer/worker.yml" \
  "Project=${PROJECT}" \
  "Application=${APPLICATION}" \
  "Service=${SERVICE_NAME}" \
  "WorkerServiceName=${WORKER_SERVICE_NAME}" \
  "Environment=${ENVIRONMENT}" \
  "EcsClusterName=${ECS_CLUSTER_NAME}" \
  "DockerRepoName=${DOCKER_REPOSITORY_NAME}" \
  "DockerImageTag=${DOCKER_IMAGE_TAG}" \
  "VpcId=${VPC_ID}" \
  "SubnetList=${SUBNET_IDS}" \
  "TaskCpu=${WORKER_TASK_CPU}" \
  "TaskMemory=${WORKER_TASK_MEMORY}" \
  "DesiredCount=${WORKER_DESIRED_COUNT}" \
  "JobsQueueArn=${JOBS_QUEUE_ARN}" \
  "JobsQueueUrl=${JOBS_QUEUE_URL}" \
  "JobsRegion=${JOBS_REGION}" \
  "JobsApiBaseUrl=${API_BASE_URL}" \
  "JobsWorkerUpdateTokenSecretArn=${JOBS_WORKER_UPDATE_TOKEN_SECRET_ARN}" \
  "FileTransferBucketName=${FILE_TRANSFER_BUCKET_NAME}" \
  "FileTransferKmsAlias=${KMS_KEY_ALIAS}" \
  "ImportKmsKeyArn=${KMS_KEY_ARN}" \
  "JobsSqsMaxNumberOfMessages=${JOBS_SQS_MAX_NUMBER_OF_MESSAGES}" \
  "JobsSqsWaitTimeSeconds=${JOBS_SQS_WAIT_TIME_SECONDS}" \
  "JobsSqsVisibilityTimeoutSeconds=${JOBS_VISIBILITY_TIMEOUT_SECONDS}" \
  "WorkerMinTaskCount=${WORKER_MIN_TASK_COUNT}" \
  "WorkerMaxTaskCount=${WORKER_MAX_TASK_COUNT}" \
  "WorkerScaleOutQueueDepthTarget=${WORKER_SCALE_OUT_QUEUE_DEPTH_TARGET}" \
  "WorkerScaleOutQueueAgeSecondsTarget=${WORKER_SCALE_OUT_QUEUE_AGE_SECONDS_TARGET}" \
  "WorkerScaleInCooldownSeconds=${WORKER_SCALE_IN_COOLDOWN_SECONDS}" \
  "WorkerScaleOutCooldownSeconds=${WORKER_SCALE_OUT_COOLDOWN_SECONDS}"

deploy_stack \
  "$OBSERVABILITY_STACK" \
  "infra/runtime/observability/ecs-observability-baseline.yml" \
  "Environment=${ENVIRONMENT}" \
  "Project=${PROJECT}" \
  "Application=${APPLICATION}" \
  "Service=${SERVICE_NAME}" \
  "EcsClusterName=${ECS_CLUSTER_NAME}" \
  "EcsServiceName=${API_ECS_SERVICE_NAME}" \
  "AlbFullName=${ALB_FULL_NAME}" \
  "TargetGroupFullName=${BLUE_TARGET_GROUP_FULL_NAME}" \
  "LogGroupName=${SERVICE_LOG_GROUP_NAME}" \
  "AlarmActionArn=${ALARM_ACTION_ARN}" \
  "MinTaskCount=${OBSERVABILITY_MIN_TASK_COUNT}" \
  "MaxTaskCount=${OBSERVABILITY_MAX_TASK_COUNT}" \
  "TargetCpuUtilizationPercent=${OBSERVABILITY_CPU_TARGET}" \
  "TargetMemoryUtilizationPercent=${OBSERVABILITY_MEMORY_TARGET}"

deploy_stack \
  "$BASE_URL_STACK" \
  "infra/nova/deploy/service-base-url-ssm.yml" \
  "Environment=${ENVIRONMENT}" \
  "ServiceName=${SERVICE_NAME}" \
  "ServiceBaseUrl=${API_BASE_URL}"

echo "==> Runtime convergence complete for ${ENVIRONMENT}"
echo "Base URL: ${API_BASE_URL}"
echo "Transfer bucket: ${FILE_TRANSFER_BUCKET_NAME}"
echo "Queue URL: ${JOBS_QUEUE_URL}"
echo "Rollback alarms: ${ROLLBACK_ALARM_PRIMARY}, ${ROLLBACK_ALARM_SECONDARY}"
