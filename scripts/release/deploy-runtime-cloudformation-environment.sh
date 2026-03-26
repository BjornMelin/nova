#!/usr/bin/env bash
set -euo pipefail

# Canonical operator path for converging a Nova runtime environment to the
# current file-transfer module topology using change-set-first CloudFormation
# deploys.
#
# Default posture applied by this operator when related override environment
# variables are left unset:
# - RUNTIME_COST_MODE is required and selects standard, saver, or paused posture
# - AssignPublicIp=DISABLED
# - FileTransferAsyncEnabled=true
# - ECS service stack owns the task role and cache-secret wiring

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

reject_legacy_env() {
  local name="$1"
  local reason="$2"
  if [ -n "${!name+x}" ]; then
    echo "Unsupported legacy environment variable: ${name}. ${reason}" >&2
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
  local timestamp
  local stack_prefix
  local change_set_name
  local waiter_name="stack-create-complete"

  timestamp="$(date +%Y%m%d%H%M%S)"
  stack_prefix="${stack_name:0:110}"
  change_set_name="${stack_prefix}-cs-${timestamp}"

  [ -f "$template_file" ] || {
    echo "Missing template file: $template_file" >&2
    exit 1
  }

  if stack_exists "$stack_name"; then
    waiter_name="stack-update-complete"
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

  local waiter_status=0
  set +e
  aws cloudformation wait change-set-create-complete \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --change-set-name "$change_set_name" >/dev/null 2>&1
  waiter_status=$?
  set -e

  local status=""
  local reason=""
  status="$(aws cloudformation describe-change-set \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --change-set-name "$change_set_name" \
    --query "Status" \
    --output text)"
  reason="$(aws cloudformation describe-change-set \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --change-set-name "$change_set_name" \
    --query "StatusReason" \
    --output text)"

  if [ "$waiter_status" -ne 0 ]; then
    echo "==> ${stack_name}: change set waiter returned ${waiter_status}; checking status" >&2
  fi

  if [ "$status" = "FAILED" ]; then
    if [[ "$reason" == *"didn't contain changes"* ]] || [[ "$reason" == *"No updates are to be performed"* ]]; then
      echo "==> ${stack_name}: no changes"
      return 0
    fi

    echo "CloudFormation change set failed for ${stack_name}: ${reason}" >&2
    aws cloudformation describe-change-set \
      --region "$AWS_REGION" \
      --stack-name "$stack_name" \
      --change-set-name "$change_set_name" \
      --output json >&2 || true
    exit 1
  fi

  if [ "$waiter_status" -ne 0 ] && [ "$status" != "CREATE_COMPLETE" ]; then
    echo "CloudFormation change set did not complete for ${stack_name}: status=${status} reason=${reason}" >&2
    aws cloudformation describe-change-set \
      --region "$AWS_REGION" \
      --stack-name "$stack_name" \
      --change-set-name "$change_set_name" \
      --output json >&2 || true
    exit 1
  fi

  describe_validation_events "$stack_name" "$change_set_name"

  echo "==> ${stack_name}: execute change set"
  aws cloudformation execute-change-set \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --change-set-name "$change_set_name" >/dev/null

  aws cloudformation wait "$waiter_name" \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" >/dev/null

  echo "==> ${stack_name}: complete"
}

delete_stack_if_exists() {
  local stack_name="$1"
  if ! stack_exists "$stack_name"; then
    echo "==> ${stack_name}: stack not found, skipping delete"
    return 0
  fi
  echo "==> ${stack_name}: delete stack"
  aws cloudformation delete-stack \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" >/dev/null
  aws cloudformation wait stack-delete-complete \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" >/dev/null
  echo "==> ${stack_name}: deleted"
}

reject_manual_alb_ingress_overrides() {
  local manual_sources=()
  [ -n "${ALB_INGRESS_PREFIX_LIST_ID:-}" ] && manual_sources+=("ALB_INGRESS_PREFIX_LIST_ID")
  [ -n "${ALB_INGRESS_CIDR:-}" ] && manual_sources+=("ALB_INGRESS_CIDR")
  [ -n "${ALB_INGRESS_SOURCE_SG_ID:-}" ] && manual_sources+=("ALB_INGRESS_SOURCE_SG_ID")

  if [ "${#manual_sources[@]}" -gt 0 ]; then
    echo "Unsupported runtime deploy override(s): ${manual_sources[*]}. The canonical operator path now resolves the CloudFront managed prefix list and applies it to the ALB ingress automatically." >&2
    exit 1
  fi
}

json_field_present() {
  local field="$1"
  jq -e --arg field "$field" '.[$field] != null' <<<"$ENV_VARS_JSON" >/dev/null
}

json_field_value() {
  local field="$1"
  jq -r --arg field "$field" '
    if .[$field] == null then "" else .[$field] | tostring end
  ' <<<"$ENV_VARS_JSON"
}

append_json_parameter_override() {
  local json_field="$1"
  local parameter_name="$2"

  if json_field_present "$json_field"; then
    printf "%s=%s" "$parameter_name" "$(json_field_value "$json_field")"
  fi
}

runtime_config_contract_path() {
  printf "%s" "${NOVA_REPO_ROOT}/packages/contracts/fixtures/runtime_config_contract.json"
}

runtime_env_json_override_pairs() {
  local contract_path
  contract_path="$(runtime_config_contract_path)"
  jq -r '
    .env_vars_json.supported_overrides[]
    | [.env_var, .cloudformation_parameter]
    | @tsv
  ' "$contract_path"
}

ensure_runtime_env_json_contract() {
  local contract_path
  local allowed_keys_json
  local forbidden_keys_json
  contract_path="$(runtime_config_contract_path)"
  [ -f "$contract_path" ] || {
    echo "Missing runtime config contract artifact: $contract_path" >&2
    exit 1
  }
  allowed_keys_json="$(
    jq -c '[.env_vars_json.supported_overrides[].env_var]' "$contract_path"
  )"
  forbidden_keys_json="$(
    jq -c '[.env_vars_json.forbidden_keys[]]' "$contract_path"
  )"

  jq -e 'type == "object"' <<<"$ENV_VARS_JSON" >/dev/null || {
    echo "ENV_VARS_JSON must be a JSON object." >&2
    exit 1
  }

  local non_scalar_fields=""
  non_scalar_fields="$(
    jq -r '
      to_entries[]
      | select((.value | type) == "array" or (.value | type) == "object")
      | .key
    ' <<<"$ENV_VARS_JSON"
  )"
  if [ -n "$non_scalar_fields" ]; then
    echo "ENV_VARS_JSON contains non-scalar values; append_json_parameter_override/json_field_value require scalar values only:" >&2
    while IFS= read -r field; do
      [ -n "$field" ] && echo "  - $field" >&2
    done <<<"$non_scalar_fields"
    exit 1
  fi

  local null_fields=""
  null_fields="$(
    jq -r '
      to_entries[]
      | select(.value == null)
      | .key
    ' <<<"$ENV_VARS_JSON"
  )"
  if [ -n "$null_fields" ]; then
    echo "ENV_VARS_JSON contains null values; remove the key or set an appropriate typed value (number/boolean/enum) instead of null:" >&2
    while IFS= read -r field; do
      [ -n "$field" ] && echo "  - $field" >&2
    done <<<"$null_fields"
    exit 1
  fi

  local unknown_fields=""
  unknown_fields="$(
    jq -r --argjson allowed "$allowed_keys_json" '
      keys_unsorted - $allowed
      | .[]
    ' <<<"$ENV_VARS_JSON"
  )"

  if [ -n "$unknown_fields" ]; then
    echo "ENV_VARS_JSON contains unsupported keys:" >&2
    while IFS= read -r field; do
      [ -n "$field" ] && echo "  - $field" >&2
    done <<<"$unknown_fields"
    exit 1
  fi

  local forbidden_fields=""
  forbidden_fields="$(
    jq -r --argjson forbidden "$forbidden_keys_json" '
      keys_unsorted | map(select(. as $key | $forbidden | index($key)))
      | .[]
    ' <<<"$ENV_VARS_JSON"
  )"

  if [ -n "$forbidden_fields" ]; then
    echo "ENV_VARS_JSON contains forbidden keys from the runtime contract:" >&2
    while IFS= read -r field; do
      [ -n "$field" ] && echo "  - $field" >&2
    done <<<"$forbidden_fields"
    exit 1
  fi

}

resolve_ecs_infrastructure_role() {
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

  echo "Missing a usable ECS infrastructure role output in ${stack_name}." >&2
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

resolve_cloudfront_origin_prefix_list_id() {
  local prefix_list_name="com.amazonaws.global.cloudfront.origin-facing"
  local prefix_list_id=""
  prefix_list_id="$(aws ec2 describe-managed-prefix-lists \
    --region "$AWS_REGION" \
    --filters "Name=prefix-list-name,Values=${prefix_list_name}" \
    --query "PrefixLists[0].PrefixListId" \
    --output text)"

  if [ -z "$prefix_list_id" ] || [ "$prefix_list_id" = "None" ]; then
    echo "Could not resolve the CloudFront managed prefix list (${prefix_list_name}) in ${AWS_REGION}." >&2
    exit 1
  fi

  printf "%s" "$prefix_list_id"
}

require_cmd aws
require_cmd jq

AWS_REGION="${AWS_REGION:-us-east-1}"
CONTROL_PLANE_PROJECT="${CONTROL_PLANE_PROJECT:-nova}"
CONTROL_PLANE_APPLICATION="${CONTROL_PLANE_APPLICATION:-ci}"
ALB_SCHEME="${ALB_SCHEME:-internal}"
ENABLE_ALB_ACCESS_LOGS="${ENABLE_ALB_ACCESS_LOGS:-false}"
ENABLE_BLUE_GREEN_TEST_LISTENER="${ENABLE_BLUE_GREEN_TEST_LISTENER:-false}"
BLUE_GREEN_TEST_LISTENER_PORT="${BLUE_GREEN_TEST_LISTENER_PORT:-8443}"
ASSIGN_PUBLIC_IP="${ASSIGN_PUBLIC_IP:-DISABLED}"
API_RUNTIME_PROFILE="${API_RUNTIME_PROFILE:-standard}"
API_LISTENER_RULE_PRIORITY="${API_LISTENER_RULE_PRIORITY:-100}"
FILE_TRANSFER_ASYNC_ENABLED="${FILE_TRANSFER_ASYNC_ENABLED:-true}"
WORKER_DESIRED_COUNT="${WORKER_DESIRED_COUNT:-1}"
WORKER_MIN_TASK_COUNT="${WORKER_MIN_TASK_COUNT:-1}"
WORKER_MAX_TASK_COUNT="${WORKER_MAX_TASK_COUNT:-20}"
WORKER_TASK_CPU="${WORKER_TASK_CPU:-1024}"
WORKER_TASK_MEMORY="${WORKER_TASK_MEMORY:-2048}"
WORKER_SCALE_OUT_QUEUE_DEPTH_TARGET="${WORKER_SCALE_OUT_QUEUE_DEPTH_TARGET:-100}"
WORKER_SCALE_OUT_QUEUE_AGE_SECONDS_TARGET="${WORKER_SCALE_OUT_QUEUE_AGE_SECONDS_TARGET:-60}"
WORKER_SCALE_IN_COOLDOWN_SECONDS="${WORKER_SCALE_IN_COOLDOWN_SECONDS:-120}"
WORKER_SCALE_OUT_COOLDOWN_SECONDS="${WORKER_SCALE_OUT_COOLDOWN_SECONDS:-60}"
WORKER_STACK_ACTION="${WORKER_STACK_ACTION:-deploy}"
OBSERVABILITY_CPU_TARGET="${OBSERVABILITY_CPU_TARGET:-60}"
OBSERVABILITY_MEMORY_TARGET="${OBSERVABILITY_MEMORY_TARGET:-70}"
RUNTIME_COST_MODE="${RUNTIME_COST_MODE:-}"
KMS_ALIAS="${KMS_ALIAS:-${PROJECT:-}-${APPLICATION:-}-${ENVIRONMENT:-}}"
FILE_TRANSFER_UPLOAD_PREFIX="${FILE_TRANSFER_UPLOAD_PREFIX:-uploads/}"
FILE_TRANSFER_EXPORT_PREFIX="${FILE_TRANSFER_EXPORT_PREFIX:-exports/}"
FILE_TRANSFER_TMP_PREFIX="${FILE_TRANSFER_TMP_PREFIX:-tmp/}"
JOBS_QUEUE_NAME="${JOBS_QUEUE_NAME:-${PROJECT:-}-${APPLICATION:-}-${SERVICE_NAME:-}-${ENVIRONMENT:-}-jobs}"
JOBS_DEAD_LETTER_QUEUE_NAME="${JOBS_DEAD_LETTER_QUEUE_NAME:-${PROJECT:-}-${APPLICATION:-}-${SERVICE_NAME:-}-${ENVIRONMENT:-}-jobs-dlq}"
JOBS_TABLE_NAME="${JOBS_TABLE_NAME:-${PROJECT:-}-${APPLICATION:-}-${SERVICE_NAME:-}-${ENVIRONMENT:-}-jobs}"
ACTIVITY_TABLE_NAME="${ACTIVITY_TABLE_NAME:-${PROJECT:-}-${APPLICATION:-}-${SERVICE_NAME:-}-${ENVIRONMENT:-}-activity}"
IDEMPOTENCY_TABLE_NAME="${IDEMPOTENCY_TABLE_NAME:-${PROJECT:-}-${APPLICATION:-}-${SERVICE_NAME:-}-${ENVIRONMENT:-}-idempotency}"
JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS="${JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS:-120}"
if ! [[ "$JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "Error: JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS must be a whole number" >&2
  exit 1
fi
if [ "$JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS" -lt 1 ] || [ "$JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS" -gt 43200 ]; then
  echo "Error: JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS must be between 1 and 43200 (12 hours)" >&2
  exit 1
fi
JOBS_MESSAGE_RETENTION_SECONDS="${JOBS_MESSAGE_RETENTION_SECONDS:-345600}"
JOBS_MAX_RECEIVE_COUNT="${JOBS_MAX_RECEIVE_COUNT:-5}"

require_env AWS_ACCOUNT_ID
require_env PROJECT
require_env APPLICATION
require_env ENVIRONMENT
require_env NOVA_REPO_ROOT
require_env VPC_ID
require_env SUBNET_IDS
require_env PUBLIC_HOSTED_ZONE_ID
require_env ALB_NAME
require_env ALB_HOSTED_ZONE_NAME
require_env ALB_DNS_NAME
require_env ECS_CLUSTER_NAME
require_env SERVICE_NAME
WORKER_SERVICE_NAME="${WORKER_SERVICE_NAME:-${SERVICE_NAME}-worker}"
require_env SERVICE_DNS
require_env DOCKER_REPOSITORY_NAME
require_env IMAGE_DIGEST
require_env OWNER_TAG
require_env ALARM_ACTION_ARN
require_env FILE_TRANSFER_BUCKET_BASE_NAME
require_env FILE_TRANSFER_CORS_ALLOWED_ORIGINS
require_env ENV_VARS_JSON

reject_legacy_env \
  ECS_INFRASTRUCTURE_ROLE_ARN \
  "The deploy operator now resolves the ECS infrastructure role from the Nova IAM control-plane stack."
reject_legacy_env \
  TASK_ROLE_ARN \
  "The ECS service stack now owns the repo-managed task role; stop supplying TaskRole overrides."
reject_legacy_env \
  TASK_EXECUTION_SECRET_ARNS \
  "The ECS service stack now scopes execution-role secret access internally; remove this legacy override."
reject_legacy_env \
  TASK_EXECUTION_SSM_PARAMETER_ARNS \
  "The ECS service stack no longer accepts generic execution-role SSM secret wiring."

if [ "$ENVIRONMENT" != "dev" ] && [ "$ENVIRONMENT" != "prod" ]; then
  echo "ENVIRONMENT must be dev or prod." >&2
  exit 1
fi

if [ "$AWS_REGION" != "us-east-1" ]; then
  echo "AWS_REGION must be us-east-1 because the CloudFront edge, CLOUDFRONT-scope WAF, and ACM viewer certificate are deployed there." >&2
  exit 1
fi

if [ -z "$RUNTIME_COST_MODE" ]; then
  echo "Missing required environment variable: RUNTIME_COST_MODE (standard|saver|paused)." >&2
  exit 1
fi

case "$RUNTIME_COST_MODE" in
  standard)
    API_DESIRED_COUNT="${API_DESIRED_COUNT:-2}"
    API_TASK_CPU="${API_TASK_CPU:-2048}"
    API_TASK_MEMORY="${API_TASK_MEMORY:-8192}"
    ENABLE_WORKER="${ENABLE_WORKER:-true}"
    WORKER_STACK_ACTION="deploy"
    OBSERVABILITY_ENABLED="${OBSERVABILITY_ENABLED:-true}"
    OBSERVABILITY_MIN_TASK_COUNT="${OBSERVABILITY_MIN_TASK_COUNT:-2}"
    OBSERVABILITY_MAX_TASK_COUNT="${OBSERVABILITY_MAX_TASK_COUNT:-20}"
    ;;
  saver)
    API_DESIRED_COUNT="${API_DESIRED_COUNT:-1}"
    API_TASK_CPU="${API_TASK_CPU:-512}"
    API_TASK_MEMORY="${API_TASK_MEMORY:-1024}"
    ENABLE_WORKER="${ENABLE_WORKER:-true}"
    WORKER_STACK_ACTION="deploy"
    OBSERVABILITY_ENABLED="${OBSERVABILITY_ENABLED:-true}"
    OBSERVABILITY_MIN_TASK_COUNT="${OBSERVABILITY_MIN_TASK_COUNT:-1}"
    OBSERVABILITY_MAX_TASK_COUNT="${OBSERVABILITY_MAX_TASK_COUNT:-2}"
    ;;
  paused)
    API_DESIRED_COUNT="${API_DESIRED_COUNT:-0}"
    API_TASK_CPU="${API_TASK_CPU:-512}"
    API_TASK_MEMORY="${API_TASK_MEMORY:-1024}"
    ENABLE_WORKER="${ENABLE_WORKER:-false}"
    WORKER_STACK_ACTION="delete"
    OBSERVABILITY_ENABLED="${OBSERVABILITY_ENABLED:-false}"
    OBSERVABILITY_MIN_TASK_COUNT="${OBSERVABILITY_MIN_TASK_COUNT:-1}"
    OBSERVABILITY_MAX_TASK_COUNT="${OBSERVABILITY_MAX_TASK_COUNT:-2}"
    ;;
  *)
    echo "RUNTIME_COST_MODE must be one of: standard, saver, paused." >&2
    exit 1
    ;;
esac

reject_manual_alb_ingress_overrides
ensure_runtime_env_json_contract

RUNTIME_BUCKET_NAME="${FILE_TRANSFER_BUCKET_BASE_NAME}-${AWS_REGION}-${AWS_ACCOUNT_ID}"
ARTIFACT_BUCKET_NAME="$(resolve_artifact_bucket_name)"
if [ -n "$ARTIFACT_BUCKET_NAME" ] && [ "$RUNTIME_BUCKET_NAME" = "$ARTIFACT_BUCKET_NAME" ]; then
  echo "Runtime file-transfer bucket must not reuse the CI artifact bucket." >&2
  exit 1
fi

ECS_INFRA_ROLE_ARN="$(resolve_ecs_infrastructure_role)"
CLOUDFRONT_MANAGED_PREFIX_LIST_ID="$(resolve_cloudfront_origin_prefix_list_id)"
KMS_STACK_NAME="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-kms"
ECR_STACK_NAME="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-ecr"
CLUSTER_STACK_NAME="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-cluster"
BUCKET_STACK_NAME="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-file-transfer"
ASYNC_STACK_NAME="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-async"
SERVICE_STACK_NAME="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-service"
WORKER_STACK_NAME="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-worker"
OBSERVABILITY_STACK_NAME="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-observability"
EDGE_STACK_NAME="${PROJECT}-${APPLICATION}-${ENVIRONMENT}-runtime-edge"
BASE_URL_STACK_NAME="${CONTROL_PLANE_PROJECT}-${CONTROL_PLANE_APPLICATION}-${ENVIRONMENT}-service-base-url"

KMS_KEY_ID_EXPORT="${AWS_ACCOUNT_ID}:${AWS_REGION}:${PROJECT}:KmsKeyId"
KMS_KEY_ARN_EXPORT="${AWS_ACCOUNT_ID}:${AWS_REGION}:${PROJECT}:KmsKeyArn"

echo "==> Deploy runtime foundations"
deploy_stack \
  "$KMS_STACK_NAME" \
  "infra/runtime/kms.yml" \
  "Project=${PROJECT}" \
  "KmsAlias=${KMS_ALIAS}"

deploy_stack \
  "$ECR_STACK_NAME" \
  "infra/runtime/ecr.yml" \
  "Project=${PROJECT}" \
  "Application=${APPLICATION}" \
  "Service=${SERVICE_NAME}" \
  "EcrRepoName=${DOCKER_REPOSITORY_NAME}" \
  "EcrKmsAlias=${KMS_ALIAS}" \
  "UsedByEcs=true"

cluster_args=(
  "Project=${PROJECT}"
  "Application=${APPLICATION}"
  "EcsClusterName=${ECS_CLUSTER_NAME}"
  "LoadBalancerId=dash"
  "LoadBalancerName=${ALB_NAME}"
  "LoadBalancerScheme=${ALB_SCHEME}"
  "HostedZoneName=${ALB_HOSTED_ZONE_NAME}"
  "VpcId=${VPC_ID}"
  "SubnetList=${SUBNET_IDS}"
  "AlbIngressPrefixListId=${CLOUDFRONT_MANAGED_PREFIX_LIST_ID}"
  "ImportKmsKeyId=${KMS_KEY_ID_EXPORT}"
  "LoadBalancerDNSName=${ALB_DNS_NAME}"
  "EnableLoadBalancerAccessLogs=${ENABLE_ALB_ACCESS_LOGS}"
  "EnableBlueGreenTestListener=${ENABLE_BLUE_GREEN_TEST_LISTENER}"
  "BlueGreenTestListenerPort=${BLUE_GREEN_TEST_LISTENER_PORT}"
)
if [ -n "${ALB_HOSTED_ZONE_ID:-}" ]; then
  cluster_args+=("HostedZoneId=${ALB_HOSTED_ZONE_ID}")
fi
if [ -n "${ALB_LOG_BUCKET:-}" ]; then
  cluster_args+=("LoadBalancerLogBucket=${ALB_LOG_BUCKET}")
fi

deploy_stack \
  "$CLUSTER_STACK_NAME" \
  "infra/runtime/ecs/cluster.yml" \
  "${cluster_args[@]}"

deploy_stack \
  "$BUCKET_STACK_NAME" \
  "infra/runtime/file_transfer/s3.yml" \
  "Project=${PROJECT}" \
  "Application=${APPLICATION}" \
  "Service=${SERVICE_NAME}" \
  "Environment=${ENVIRONMENT}" \
  "BucketBaseName=${FILE_TRANSFER_BUCKET_BASE_NAME}" \
  "KmsAlias=${KMS_ALIAS}" \
  "CorsAllowedOrigins=${FILE_TRANSFER_CORS_ALLOWED_ORIGINS}"

if [ "$FILE_TRANSFER_ASYNC_ENABLED" = "true" ]; then
  deploy_stack \
    "$ASYNC_STACK_NAME" \
    "infra/runtime/file_transfer/async.yml" \
    "Project=${PROJECT}" \
    "Application=${APPLICATION}" \
    "Service=${SERVICE_NAME}" \
    "Environment=${ENVIRONMENT}" \
    "JobsQueueName=${JOBS_QUEUE_NAME}" \
    "JobsDeadLetterQueueName=${JOBS_DEAD_LETTER_QUEUE_NAME}" \
    "JobsTableName=${JOBS_TABLE_NAME}" \
    "ActivityTableName=${ACTIVITY_TABLE_NAME}" \
    "IdempotencyTableName=${IDEMPOTENCY_TABLE_NAME}" \
    "JobsVisibilityTimeoutSeconds=${JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS}" \
    "JobsMessageRetentionSeconds=${JOBS_MESSAGE_RETENTION_SECONDS}" \
    "JobsMaxReceiveCount=${JOBS_MAX_RECEIVE_COUNT}" \
    "AlarmNotificationTopicArn=${ALARM_ACTION_ARN}"
fi

JOBS_QUEUE_ARN=""
JOBS_QUEUE_URL=""
JOBS_TABLE_NAME=""
JOBS_TABLE_ARN=""
ACTIVITY_TABLE_NAME=""
ACTIVITY_TABLE_ARN=""
IDEMPOTENCY_TABLE_NAME=""
IDEMPOTENCY_TABLE_ARN=""
if [ "$FILE_TRANSFER_ASYNC_ENABLED" = "true" ]; then
  JOBS_QUEUE_ARN="$(stack_output "$ASYNC_STACK_NAME" JobsQueueArn)"
  JOBS_QUEUE_URL="$(stack_output "$ASYNC_STACK_NAME" JobsQueueUrl)"
  JOBS_TABLE_NAME="$(stack_output "$ASYNC_STACK_NAME" JobsTableName)"
  JOBS_TABLE_ARN="$(stack_output "$ASYNC_STACK_NAME" JobsTableArn)"
  ACTIVITY_TABLE_NAME="$(stack_output "$ASYNC_STACK_NAME" ActivityTableName)"
  ACTIVITY_TABLE_ARN="$(stack_output "$ASYNC_STACK_NAME" ActivityTableArn)"
  IDEMPOTENCY_TABLE_NAME="$(stack_output "$ASYNC_STACK_NAME" IdempotencyTableName)"
  IDEMPOTENCY_TABLE_ARN="$(stack_output "$ASYNC_STACK_NAME" IdempotencyTableArn)"
fi

TEST_TRAFFIC_LISTENER_ARN=""
if [ "$ENABLE_BLUE_GREEN_TEST_LISTENER" = "true" ]; then
  TEST_TRAFFIC_LISTENER_ARN="$(stack_output "$CLUSTER_STACK_NAME" TestListenerArn)"
fi

service_args=(
  "Environment=${ENVIRONMENT}"
  "Project=${PROJECT}"
  "Application=${APPLICATION}"
  "Service=${SERVICE_NAME}"
  "ServiceHostedZoneId=${PUBLIC_HOSTED_ZONE_ID}"
  "EcsClusterName=${ECS_CLUSTER_NAME}"
  "LoadBalancerName=${ALB_NAME}"
  "DockerRepoName=${DOCKER_REPOSITORY_NAME}"
  "ImageDigest=${IMAGE_DIGEST}"
  "VpcId=${VPC_ID}"
  "SubnetList=${SUBNET_IDS}"
  "AssignPublicIp=${ASSIGN_PUBLIC_IP}"
  "TaskCpu=${API_TASK_CPU}"
  "TaskMemory=${API_TASK_MEMORY}"
  "DesiredCount=${API_DESIRED_COUNT}"
  "RuntimeProfile=${API_RUNTIME_PROFILE}"
  "ListenerRulePriority=${API_LISTENER_RULE_PRIORITY}"
  "EcsInfrastructureRoleArn=${ECS_INFRA_ROLE_ARN}"
  "TestTrafficListenerArn=${TEST_TRAFFIC_LISTENER_ARN}"
  "ServiceDNS=${SERVICE_DNS}"
  "AlarmArn=${ALARM_ACTION_ARN}"
  "Owner=${OWNER_TAG}"
  "FileTransferEnabled=true"
  "FileTransferBucketName=${RUNTIME_BUCKET_NAME}"
  "FileTransferUploadPrefix=${FILE_TRANSFER_UPLOAD_PREFIX}"
  "FileTransferExportPrefix=${FILE_TRANSFER_EXPORT_PREFIX}"
  "FileTransferTmpPrefix=${FILE_TRANSFER_TMP_PREFIX}"
  "FileTransferKmsAlias=${KMS_ALIAS}"
  "FileTransferAsyncEnabled=${FILE_TRANSFER_ASYNC_ENABLED}"
  "FileTransferJobsQueueArn=${JOBS_QUEUE_ARN}"
  "FileTransferJobsTableArn=${JOBS_TABLE_ARN}"
  "FileTransferActivityTableArn=${ACTIVITY_TABLE_ARN}"
  "FileTransferIdempotencyTableArn=${IDEMPOTENCY_TABLE_ARN}"
  "JobsQueueUrl=${JOBS_QUEUE_URL}"
  "JobsTableName=${JOBS_TABLE_NAME}"
  "ActivityTableName=${ACTIVITY_TABLE_NAME}"
  "IdempotencyTableName=${IDEMPOTENCY_TABLE_NAME}"
)

while IFS=$'\t' read -r json_field parameter_name; do
  parameter_override="$(append_json_parameter_override "$json_field" "$parameter_name")"
  if [ -n "$parameter_override" ]; then
    service_args+=("$parameter_override")
  fi
done < <(runtime_env_json_override_pairs)

deploy_stack \
  "$SERVICE_STACK_NAME" \
  "infra/runtime/ecs/service.yml" \
  "${service_args[@]}"

LOAD_BALANCER_ARN="$(stack_output "$CLUSTER_STACK_NAME" LoadBalancerArn)"

deploy_stack \
  "$EDGE_STACK_NAME" \
  "infra/runtime/edge/cloudfront.yml" \
  "Environment=${ENVIRONMENT}" \
  "Project=${PROJECT}" \
  "Application=${APPLICATION}" \
  "Service=${SERVICE_NAME}" \
  "LoadBalancerArn=${LOAD_BALANCER_ARN}" \
  "LoadBalancerDomainName=${ALB_DNS_NAME}" \
  "PublicHostedZoneId=${PUBLIC_HOSTED_ZONE_ID}" \
  "ServiceDNS=${SERVICE_DNS}"

SERVICE_BASE_URL="$(stack_output "$EDGE_STACK_NAME" PublicBaseUrl)"

if [ "$WORKER_STACK_ACTION" = "delete" ]; then
  delete_stack_if_exists "$WORKER_STACK_NAME"
elif [ "$ENABLE_WORKER" = "true" ] && [ "$FILE_TRANSFER_ASYNC_ENABLED" = "true" ]; then
  deploy_stack \
    "$WORKER_STACK_NAME" \
    "infra/runtime/file_transfer/worker.yml" \
    "Project=${PROJECT}" \
    "Application=${APPLICATION}" \
    "Service=${SERVICE_NAME}" \
    "WorkerServiceName=${WORKER_SERVICE_NAME}" \
    "Environment=${ENVIRONMENT}" \
    "EcsClusterName=${ECS_CLUSTER_NAME}" \
    "DockerRepoName=${DOCKER_REPOSITORY_NAME}" \
    "ImageDigest=${IMAGE_DIGEST}" \
    "VpcId=${VPC_ID}" \
    "SubnetList=${SUBNET_IDS}" \
    "TaskCpu=${WORKER_TASK_CPU}" \
    "TaskMemory=${WORKER_TASK_MEMORY}" \
    "DesiredCount=${WORKER_DESIRED_COUNT}" \
    "JobsQueueArn=${JOBS_QUEUE_ARN}" \
    "JobsQueueUrl=${JOBS_QUEUE_URL}" \
    "JobsTableName=${JOBS_TABLE_NAME}" \
    "JobsTableArn=${JOBS_TABLE_ARN}" \
    "ActivityTableName=${ACTIVITY_TABLE_NAME}" \
    "ActivityTableArn=${ACTIVITY_TABLE_ARN}" \
    "JobsVisibilityTimeoutSeconds=${JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS}" \
    "FileTransferBucketName=${RUNTIME_BUCKET_NAME}" \
    "FileTransferUploadPrefix=${FILE_TRANSFER_UPLOAD_PREFIX}" \
    "FileTransferExportPrefix=${FILE_TRANSFER_EXPORT_PREFIX}" \
    "FileTransferTmpPrefix=${FILE_TRANSFER_TMP_PREFIX}" \
    "FileTransferKmsAlias=${KMS_ALIAS}" \
    "ImportKmsKeyArn=${KMS_KEY_ARN_EXPORT}" \
    "WorkerMinTaskCount=${WORKER_MIN_TASK_COUNT}" \
    "WorkerMaxTaskCount=${WORKER_MAX_TASK_COUNT}" \
    "WorkerScaleOutQueueDepthTarget=${WORKER_SCALE_OUT_QUEUE_DEPTH_TARGET}" \
    "WorkerScaleOutQueueAgeSecondsTarget=${WORKER_SCALE_OUT_QUEUE_AGE_SECONDS_TARGET}" \
    "WorkerScaleInCooldownSeconds=${WORKER_SCALE_IN_COOLDOWN_SECONDS}" \
    "WorkerScaleOutCooldownSeconds=${WORKER_SCALE_OUT_COOLDOWN_SECONDS}"
fi

if [ "$OBSERVABILITY_ENABLED" = "true" ]; then
  LOAD_BALANCER_FULL_NAME="$(stack_output "$CLUSTER_STACK_NAME" LoadBalancerFullName)"
  BLUE_TARGET_GROUP_ARN="$(stack_output "$SERVICE_STACK_NAME" BlueTargetGroupArn)"
  BLUE_TARGET_GROUP_FULL_NAME="$(aws elbv2 describe-target-groups \
    --region "$AWS_REGION" \
    --target-group-arns "$BLUE_TARGET_GROUP_ARN" \
    --query "TargetGroups[0].TargetGroupFullName" \
    --output text)"
  KMS_KEY_ARN="${KMS_KEY_ARN:-$(stack_output "$KMS_STACK_NAME" KmsKeyArn)}"

  deploy_stack \
    "$OBSERVABILITY_STACK_NAME" \
    "infra/runtime/observability/ecs-observability-baseline.yml" \
    "Environment=${ENVIRONMENT}" \
    "Project=${PROJECT}" \
    "Application=${APPLICATION}" \
    "Service=${SERVICE_NAME}" \
    "EcsClusterName=${ECS_CLUSTER_NAME}" \
    "EcsServiceName=${PROJECT}-${APPLICATION}-${SERVICE_NAME}" \
    "AlbFullName=${LOAD_BALANCER_FULL_NAME}" \
    "TargetGroupFullName=${BLUE_TARGET_GROUP_FULL_NAME}" \
    "LogGroupName=${PROJECT}-${APPLICATION}/${SERVICE_NAME}/ecs" \
    "ManageLogGroupRetentionPolicy=false" \
    "ServiceLogKmsKeyArn=${KMS_KEY_ARN}" \
    "AlarmActionArn=${ALARM_ACTION_ARN}" \
    "MinTaskCount=${OBSERVABILITY_MIN_TASK_COUNT}" \
    "MaxTaskCount=${OBSERVABILITY_MAX_TASK_COUNT}" \
    "TargetCpuUtilizationPercent=${OBSERVABILITY_CPU_TARGET}" \
    "TargetMemoryUtilizationPercent=${OBSERVABILITY_MEMORY_TARGET}"
else
  delete_stack_if_exists "$OBSERVABILITY_STACK_NAME"
fi

deploy_stack \
  "$BASE_URL_STACK_NAME" \
  "infra/nova/deploy/service-base-url-ssm.yml" \
  "Environment=${ENVIRONMENT}" \
  "ServiceName=${SERVICE_NAME}" \
  "ServiceBaseUrl=${SERVICE_BASE_URL}"

echo
echo "Runtime environment converged successfully."
echo "Service base URL: ${SERVICE_BASE_URL}"
