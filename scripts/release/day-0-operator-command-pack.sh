#!/usr/bin/env bash
set -euo pipefail

# Day-0 operator command pack for Nova CI/CD bootstrap.
# This script provisions the release signing secret, deploys the three Nova
# CI/CD CloudFormation stacks plus foundation from this repository, configures
# GitHub secrets/variables, validates CodeConnections status, and optionally
# triggers release workflows.

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

stack_output() {
  local stack_name="$1"
  local output_key="$2"
  aws cloudformation describe-stacks \
    --region "$AWS_REGION" \
    --stack-name "$stack_name" \
    --query "Stacks[0].Outputs[?OutputKey==\`${output_key}\`].OutputValue | [0]" \
    --output text
}

validate_service_base_url() {
  local url="$1"
  local source_ref="$2"

  if [ -z "$url" ]; then
    echo "Resolved empty service base URL from: $source_ref" >&2
    exit 1
  fi
  if [[ ! "$url" =~ ^https://[^/[:space:]]+(/.*)?$ ]]; then
    echo "Service base URL must use https:// ($source_ref -> $url)" >&2
    exit 1
  fi
  if [[ "$url" =~ [[:space:]] ]]; then
    echo "Service base URL must not contain whitespace ($source_ref)" >&2
    exit 1
  fi
  if [[ "$url" == *httpbin* ]] || [[ "$url" == *placeholder* ]] || [[ "$url" == *example.com* ]] || [[ "$url" == *"<"* ]] || [[ "$url" == *">"* ]]; then
    echo "Service base URL appears to be a placeholder/test host ($source_ref -> $url)" >&2
    exit 1
  fi
}

resolve_service_base_url() {
  local environment="$1"
  local service_name="$2"
  local parameter_name="/nova/${environment}/${service_name}/base-url"
  local value=""
  local output=""

  if ! output="$(aws ssm get-parameter \
    --region "$AWS_REGION" \
    --name "$parameter_name" \
    --query 'Parameter.Value' \
    --output text 2>&1)"; then
    if [[ "$output" == *ParameterNotFound* ]]; then
      echo "Missing required SSM parameter: $parameter_name" >&2
      echo "Populate it by deploying infra/nova/deploy/service-base-url-ssm.yml first." >&2
      exit 1
    fi
    echo "$output" >&2
    exit 1
  fi

  value="$output"
  validate_service_base_url "$value" "$parameter_name"
  printf "%s" "$value"
}

require_cmd aws
require_cmd gh
require_cmd jq
require_cmd ssh-keygen

AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT="${PROJECT:-nova}"
APPLICATION="${APPLICATION:-ci}"
GITHUB_OWNER="${GITHUB_OWNER:-3M-Cloud}"
GITHUB_REPO="${GITHUB_REPO:-nova}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
SECRET_NAME="${SECRET_NAME:-nova/release/signing-key}"
NOVA_REPO_ROOT="${NOVA_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
CONNECTION_NAME="${CONNECTION_NAME:-nova-codeconnection}"
EXISTING_CONNECTION_ARN="${EXISTING_CONNECTION_ARN:-}"
CODEARTIFACT_DOMAIN_NAME="${CODEARTIFACT_DOMAIN_NAME:-cral}"
CODEARTIFACT_REPOSITORY_NAME="${CODEARTIFACT_REPOSITORY_NAME:-galaxypy}"
CODEARTIFACT_STAGING_REPOSITORY="${CODEARTIFACT_STAGING_REPOSITORY:-$CODEARTIFACT_REPOSITORY_NAME}"
CODEARTIFACT_PROD_REPOSITORY="${CODEARTIFACT_PROD_REPOSITORY:-}"
ECR_REPOSITORY_NAME="${ECR_REPOSITORY_NAME:-nova-file-api}"
ECR_REPOSITORY_URI="${ECR_REPOSITORY_URI:-${AWS_ACCOUNT_ID:-}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY_NAME}}"
ECR_REPOSITORY_ARN="${ECR_REPOSITORY_ARN:-arn:aws:ecr:${AWS_REGION}:${AWS_ACCOUNT_ID:-000000000000}:repository/${ECR_REPOSITORY_NAME}}"
NOVA_RELEASE_BUILD_PROJECT_NAME="${NOVA_RELEASE_BUILD_PROJECT_NAME:-${PROJECT}-${APPLICATION}-nova-release-build}"
NOVA_DEPLOY_VALIDATE_PROJECT_NAME="${NOVA_DEPLOY_VALIDATE_PROJECT_NAME:-${PROJECT}-${APPLICATION}-nova-deploy-validate}"
NOVA_DEPLOY_SERVICE_NAME="${NOVA_DEPLOY_SERVICE_NAME:-nova-file-api}"
NOVA_DEPLOY_DEV_STACK_NAME="${NOVA_DEPLOY_DEV_STACK_NAME:-${PROJECT}-${APPLICATION}-nova-dev}"
NOVA_DEPLOY_PROD_STACK_NAME="${NOVA_DEPLOY_PROD_STACK_NAME:-${PROJECT}-${APPLICATION}-nova-prod}"
NOVA_AUTH_DEPLOY_SERVICE_NAME="${NOVA_AUTH_DEPLOY_SERVICE_NAME:-nova-auth-api}"
NOVA_AUTH_DEPLOY_DEV_STACK_NAME="${NOVA_AUTH_DEPLOY_DEV_STACK_NAME:-${PROJECT}-${APPLICATION}-nova-auth-dev}"
NOVA_AUTH_DEPLOY_PROD_STACK_NAME="${NOVA_AUTH_DEPLOY_PROD_STACK_NAME:-${PROJECT}-${APPLICATION}-nova-auth-prod}"
NOVA_MANUAL_APPROVAL_TOPIC_ARN="${NOVA_MANUAL_APPROVAL_TOPIC_ARN:-}"
RELEASE_VALIDATION_TRUSTED_PRINCIPAL_ARN="${RELEASE_VALIDATION_TRUSTED_PRINCIPAL_ARN:-}"
TRIGGER_WORKFLOWS="${TRIGGER_WORKFLOWS:-true}"
TRIGGER_RELEASE_APPLY_DIRECT="${TRIGGER_RELEASE_APPLY_DIRECT:-false}"
ROTATE_SIGNING_KEY="${ROTATE_SIGNING_KEY:-false}"

require_env AWS_ACCOUNT_ID
require_env SIGNER_NAME
require_env SIGNER_EMAIL
require_env GITHUB_OIDC_PROVIDER_ARN
require_env NOVA_ARTIFACT_BUCKET_NAME
require_env CODEARTIFACT_PROD_REPOSITORY

if [ "$CODEARTIFACT_STAGING_REPOSITORY" = "$CODEARTIFACT_PROD_REPOSITORY" ]; then
  echo "CODEARTIFACT_STAGING_REPOSITORY and CODEARTIFACT_PROD_REPOSITORY must differ." >&2
  exit 1
fi

if [ ! -d "$NOVA_REPO_ROOT" ]; then
  echo "nova repo root not found at: $NOVA_REPO_ROOT" >&2
  exit 1
fi

IAM_TEMPLATE="$NOVA_REPO_ROOT/infra/nova/nova-iam-roles.yml"
FOUNDATION_TEMPLATE="$NOVA_REPO_ROOT/infra/nova/nova-foundation.yml"
CODEBUILD_TEMPLATE="$NOVA_REPO_ROOT/infra/nova/nova-codebuild-release.yml"
PIPELINE_TEMPLATE="$NOVA_REPO_ROOT/infra/nova/nova-ci-cd.yml"

for template in "$FOUNDATION_TEMPLATE" "$IAM_TEMPLATE" "$CODEBUILD_TEMPLATE" "$PIPELINE_TEMPLATE"; do
  if [ ! -f "$template" ]; then
    echo "Missing template file: $template" >&2
    exit 1
  fi
done

echo "==> Resolve canonical service base URLs from SSM"
NOVA_DEV_SERVICE_BASE_URL="$(resolve_service_base_url dev "$NOVA_DEPLOY_SERVICE_NAME")"
NOVA_PROD_SERVICE_BASE_URL="$(resolve_service_base_url prod "$NOVA_DEPLOY_SERVICE_NAME")"
NOVA_DEV_AUTH_SERVICE_BASE_URL="$(resolve_service_base_url dev "$NOVA_AUTH_DEPLOY_SERVICE_NAME")"
NOVA_PROD_AUTH_SERVICE_BASE_URL="$(resolve_service_base_url prod "$NOVA_AUTH_DEPLOY_SERVICE_NAME")"
echo "Resolved dev base URL: $NOVA_DEV_SERVICE_BASE_URL"
echo "Resolved prod base URL: $NOVA_PROD_SERVICE_BASE_URL"
echo "Resolved auth dev base URL: $NOVA_DEV_AUTH_SERVICE_BASE_URL"
echo "Resolved auth prod base URL: $NOVA_PROD_AUTH_SERVICE_BASE_URL"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

KEY_PATH="$TMP_DIR/release_signing_key"
SECRET_PATH="$TMP_DIR/release_signing_secret.json"

echo "==> Step 1/7: generate signing key and upsert secret"
if aws secretsmanager describe-secret --region "$AWS_REGION" --secret-id "$SECRET_NAME" >/dev/null 2>&1 \
  && [ "$ROTATE_SIGNING_KEY" != "true" ]; then
  echo "Existing signing secret found; reusing current key (set ROTATE_SIGNING_KEY=true to rotate)."
  aws secretsmanager get-secret-value \
    --region "$AWS_REGION" \
    --secret-id "$SECRET_NAME" \
    --query SecretString \
    --output text > "$SECRET_PATH"
else
  if [ "$ROTATE_SIGNING_KEY" = "true" ]; then
    echo "ROTATE_SIGNING_KEY=true; generating a new signing key."
  fi
  ssh-keygen -t ed25519 -C "$SIGNER_EMAIL" -N "" -f "$KEY_PATH" >/dev/null
  jq -n \
    --arg private_key "$(cat "$KEY_PATH")" \
    --arg public_key "$(cat "$KEY_PATH.pub")" \
    --arg signer_name "$SIGNER_NAME" \
    --arg signer_email "$SIGNER_EMAIL" \
    '{private_key:$private_key,public_key:$public_key,signer_name:$signer_name,signer_email:$signer_email}' \
    > "$SECRET_PATH"

  if aws secretsmanager describe-secret --region "$AWS_REGION" --secret-id "$SECRET_NAME" >/dev/null 2>&1; then
    aws secretsmanager put-secret-value \
      --region "$AWS_REGION" \
      --secret-id "$SECRET_NAME" \
      --secret-string "file://$SECRET_PATH" >/dev/null
  else
    aws secretsmanager create-secret \
      --region "$AWS_REGION" \
      --name "$SECRET_NAME" \
      --description "Nova release SSH signing key" \
      --secret-string "file://$SECRET_PATH" >/dev/null
  fi
fi

RELEASE_SIGNING_SECRET_ARN="$(aws secretsmanager describe-secret \
  --region "$AWS_REGION" \
  --secret-id "$SECRET_NAME" \
  --query 'ARN' \
  --output text)"

FOUNDATION_STACK_NAME="${PROJECT}-${APPLICATION}-nova-foundation"
IAM_STACK_NAME="${PROJECT}-${APPLICATION}-nova-iam-roles"
CODEBUILD_STACK_NAME="${PROJECT}-${APPLICATION}-nova-codebuild-release"
PIPELINE_STACK_NAME="${PROJECT}-${APPLICATION}-nova-ci-cd"

FOUNDATION_EXISTING_ARTIFACT_BUCKET_NAME="$NOVA_ARTIFACT_BUCKET_NAME"
FOUNDATION_ARTIFACT_BUCKET_NAME=""
head_bucket_output=""
if head_bucket_output="$(aws s3api head-bucket --bucket "$NOVA_ARTIFACT_BUCKET_NAME" 2>&1)"; then
  echo "Artifact bucket exists; foundation will import existing bucket."
else
  if [[ "$head_bucket_output" == *NotFound* ]] || [[ "$head_bucket_output" == *"Not Found"* ]] || [[ "$head_bucket_output" == *NoSuchBucket* ]]; then
    echo "Artifact bucket not found; foundation will create bucket named $NOVA_ARTIFACT_BUCKET_NAME."
    FOUNDATION_EXISTING_ARTIFACT_BUCKET_NAME=""
    FOUNDATION_ARTIFACT_BUCKET_NAME="$NOVA_ARTIFACT_BUCKET_NAME"
  else
    echo "$head_bucket_output" >&2
    exit 1
  fi
fi

echo "==> Step 2/8: deploy foundation stack"
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$FOUNDATION_STACK_NAME" \
  --template-file "$FOUNDATION_TEMPLATE" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Project="$PROJECT" \
    Application="$APPLICATION" \
    ExistingArtifactBucketName="$FOUNDATION_EXISTING_ARTIFACT_BUCKET_NAME" \
    ArtifactBucketName="$FOUNDATION_ARTIFACT_BUCKET_NAME" \
    CodeArtifactDomainName="$CODEARTIFACT_DOMAIN_NAME" \
    CodeArtifactRepositoryName="$CODEARTIFACT_STAGING_REPOSITORY" \
    EcrRepositoryArn="$ECR_REPOSITORY_ARN" \
    EcrRepositoryName="$ECR_REPOSITORY_NAME" \
    EcrRepositoryUri="$ECR_REPOSITORY_URI" \
    ExistingConnectionArn="$EXISTING_CONNECTION_ARN" \
    ManualApprovalTopicArn="$NOVA_MANUAL_APPROVAL_TOPIC_ARN"

echo "==> Step 3/8: deploy IAM roles stack"
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$IAM_STACK_NAME" \
  --template-file "$IAM_TEMPLATE" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Project="$PROJECT" \
    Application="$APPLICATION" \
    FoundationStackName="$FOUNDATION_STACK_NAME" \
    RepositoryOwner="$GITHUB_OWNER" \
    RepositoryName="$GITHUB_REPO" \
    MainBranchName="$MAIN_BRANCH" \
    GitHubOidcProviderArn="$GITHUB_OIDC_PROVIDER_ARN" \
    ReleaseSigningSecretArn="$RELEASE_SIGNING_SECRET_ARN" \
    CodeArtifactPromotionSourceRepositoryName="$CODEARTIFACT_STAGING_REPOSITORY" \
    CodeArtifactPromotionDestinationRepositoryName="$CODEARTIFACT_PROD_REPOSITORY" \
    ReleaseValidationTrustedPrincipalArn="$RELEASE_VALIDATION_TRUSTED_PRINCIPAL_ARN" \
    ExistingConnectionArn="$EXISTING_CONNECTION_ARN" \
    ManualApprovalTopicArn="$NOVA_MANUAL_APPROVAL_TOPIC_ARN"

echo "==> Step 4/8: deploy CodeBuild stack"
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$CODEBUILD_STACK_NAME" \
  --template-file "$CODEBUILD_TEMPLATE" \
  --parameter-overrides \
    Project="$PROJECT" \
    Application="$APPLICATION" \
    FoundationStackName="$FOUNDATION_STACK_NAME" \
    IamRolesStackName="$IAM_STACK_NAME" \
    FileDockerfilePath="apps/nova_file_api_service/Dockerfile" \
    AuthDockerfilePath="apps/nova_auth_api_service/Dockerfile" \
    DockerBuildContext="." \
    ReleaseBuildspecPath="buildspecs/buildspec-release.yml" \
    ValidateBuildspecPath="buildspecs/buildspec-deploy-validate.yml"

echo "==> Step 5/8: deploy CodePipeline stack"
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$PIPELINE_STACK_NAME" \
  --template-file "$PIPELINE_TEMPLATE" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Project="$PROJECT" \
    Application="$APPLICATION" \
    FoundationStackName="$FOUNDATION_STACK_NAME" \
    IamRolesStackName="$IAM_STACK_NAME" \
    CodeBuildStackName="$CODEBUILD_STACK_NAME" \
    RepositoryOwner="$GITHUB_OWNER" \
    RepositoryName="$GITHUB_REPO" \
    MainBranchName="$MAIN_BRANCH" \
    ConnectionName="$CONNECTION_NAME" \
    ExistingConnectionArn="$EXISTING_CONNECTION_ARN" \
    DeployServiceName="$NOVA_DEPLOY_SERVICE_NAME" \
    DeployDevStackName="$NOVA_DEPLOY_DEV_STACK_NAME" \
    AuthDeployServiceName="$NOVA_AUTH_DEPLOY_SERVICE_NAME" \
    AuthDeployDevStackName="$NOVA_AUTH_DEPLOY_DEV_STACK_NAME" \
    AuthDeployProdStackName="$NOVA_AUTH_DEPLOY_PROD_STACK_NAME" \
    DevAuthServiceBaseUrl="$NOVA_DEV_AUTH_SERVICE_BASE_URL" \
    ProdAuthServiceBaseUrl="$NOVA_PROD_AUTH_SERVICE_BASE_URL" \
    AuthValidationCanonicalPaths="GET:/v1/health/live,POST:/v1/token/verify,POST:/v1/token/introspect" \
    DeployProdStackName="$NOVA_DEPLOY_PROD_STACK_NAME" \
    DevServiceBaseUrl="$NOVA_DEV_SERVICE_BASE_URL" \
    ProdServiceBaseUrl="$NOVA_PROD_SERVICE_BASE_URL" \
    ManualApprovalTopicArn="$NOVA_MANUAL_APPROVAL_TOPIC_ARN"

RELEASE_AWS_ROLE_ARN="$(stack_output "$IAM_STACK_NAME" "GitHubOIDCReleaseRoleArn")"
CODEPIPELINE_NAME="$(stack_output "$PIPELINE_STACK_NAME" "PipelineName")"
CONNECTION_ARN="$(stack_output "$PIPELINE_STACK_NAME" "ConnectionArn")"

if [ -z "$RELEASE_AWS_ROLE_ARN" ] || [ "$RELEASE_AWS_ROLE_ARN" = "None" ]; then
  echo "Unable to read GitHubOIDCReleaseRoleArn output" >&2
  exit 1
fi

if [ -z "$CODEPIPELINE_NAME" ] || [ "$CODEPIPELINE_NAME" = "None" ]; then
  echo "Unable to read PipelineName output" >&2
  exit 1
fi

if [ -z "$CONNECTION_ARN" ] || [ "$CONNECTION_ARN" = "None" ]; then
  echo "Unable to read ConnectionArn output" >&2
  exit 1
fi

GH_REPO="${GITHUB_OWNER}/${GITHUB_REPO}"

echo "==> Step 6/8: configure GitHub secrets and variable for $GH_REPO"
gh secret set RELEASE_SIGNING_SECRET_ID --repo "$GH_REPO" --body "$SECRET_NAME"
gh secret set RELEASE_AWS_ROLE_ARN --repo "$GH_REPO" --body "$RELEASE_AWS_ROLE_ARN"
gh variable set AWS_REGION --repo "$GH_REPO" --body "$AWS_REGION"
gh variable set CODEARTIFACT_STAGING_REPOSITORY --repo "$GH_REPO" --body "$CODEARTIFACT_STAGING_REPOSITORY"
gh variable set CODEARTIFACT_PROD_REPOSITORY --repo "$GH_REPO" --body "$CODEARTIFACT_PROD_REPOSITORY"

echo "==> Step 7/8: validate CodeConnections status"
CONNECTION_STATUS="$(aws codeconnections get-connection \
  --region "$AWS_REGION" \
  --connection-arn "$CONNECTION_ARN" \
  --query 'Connection.ConnectionStatus' \
  --output text)"

echo "Connection status: $CONNECTION_STATUS"
if [ "$CONNECTION_STATUS" != "AVAILABLE" ]; then
  echo "Action required: activate connection in AWS Console before expecting source triggers."
fi

echo "==> Step 8/8: trigger release workflows"
if [ "$TRIGGER_WORKFLOWS" = "true" ]; then
  gh workflow run "Nova Release Plan" --repo "$GH_REPO" --ref "$MAIN_BRANCH"
  if [ "$TRIGGER_RELEASE_APPLY_DIRECT" = "true" ]; then
    gh workflow run "Nova Release Apply" --repo "$GH_REPO" --ref "$MAIN_BRANCH"
  fi
else
  echo "Skipping workflow dispatch because TRIGGER_WORKFLOWS=$TRIGGER_WORKFLOWS"
fi

echo
echo "Done. Operator handoff values:"
echo "RELEASE_AWS_ROLE_ARN=$RELEASE_AWS_ROLE_ARN"
echo "CONNECTION_ARN=$CONNECTION_ARN"
echo "CODEPIPELINE_NAME=$CODEPIPELINE_NAME"
echo
echo "Follow-up verification commands:"
echo "aws codepipeline list-pipeline-executions --region \"$AWS_REGION\" --pipeline-name \"$CODEPIPELINE_NAME\" --max-results 5"
echo "aws codepipeline get-pipeline-state --region \"$AWS_REGION\" --name \"$CODEPIPELINE_NAME\""
