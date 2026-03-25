# Day-0 Operator Checklist (Minimal Path)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-17

## Purpose

Run first-time Nova CI/CD provisioning and release promotion using the shortest
safe operator path.

## Prerequisites

1. AWS CLI v2 authenticated.
2. GitHub CLI authenticated.
3. Repository admin access to the target `${GITHUB_OWNER}/${GITHUB_REPO}` pair.
4. Required environment values prepared.
5. Runtime stacks already deployed for `dev` and `prod` (see
   [deploy-runtime-cloudformation-environments.md](./deploy-runtime-cloudformation-environments.md)).
6. `jq` and `ssh-keygen` are installed.

## Inputs

- `${AWS_REGION}` (required, e.g., `us-east-1`)
- `${AWS_ACCOUNT_ID}` (optional; derived from STS when unset)
- `${PROJECT}` (default `nova`)
- `${APPLICATION}` (default `ci`)
- `${GITHUB_OWNER}` (required; explicit GitHub org or user target)
- `${GITHUB_REPO}` (required; explicit GitHub repository target)
- `${EXISTING_CONNECTION_ARN}` (optional, prefer
  `arn:aws:codeconnections:us-east-1:…:connection/xxxxxxxx`;
  legacy `codestar-connections` ARNs remain supported only for migrated
  environments)
- `${CODEARTIFACT_DOMAIN}` (required)
- `${CODEARTIFACT_STAGING_REPOSITORY}` (required)
- `${CODEARTIFACT_PROD_REPOSITORY}` (required; must differ from staging)
- `${ECR_REPOSITORY_NAME}` (optional; default `nova-file-api`)
- `${ECR_REPOSITORY_URI}` (optional; derived when unset)
- `${ECR_REPOSITORY_ARN}` (optional; derived when unset)
- `${SIGNER_NAME}` (required)
- `${SIGNER_EMAIL}` (required)
- `${NOVA_ARTIFACT_BUCKET_NAME}` (required)

## Step-by-step commands

### Step 1: Export required values

```bash
export AWS_REGION="${AWS_REGION:?Set AWS_REGION}"
export PROJECT="${PROJECT:-nova}"
export APPLICATION="${APPLICATION:-ci}"
export GITHUB_OWNER="${GITHUB_OWNER:?Set GITHUB_OWNER}"
export GITHUB_REPO="${GITHUB_REPO:?Set GITHUB_REPO}"
export CODEARTIFACT_DOMAIN="${CODEARTIFACT_DOMAIN:?Set CODEARTIFACT_DOMAIN}"
export CODEARTIFACT_STAGING_REPOSITORY="${CODEARTIFACT_STAGING_REPOSITORY:?Set CODEARTIFACT_STAGING_REPOSITORY}"
export CODEARTIFACT_PROD_REPOSITORY="${CODEARTIFACT_PROD_REPOSITORY:?Set CODEARTIFACT_PROD_REPOSITORY}"
export EXISTING_CONNECTION_ARN="${EXISTING_CONNECTION_ARN:-}"
export ECR_REPOSITORY_NAME="${ECR_REPOSITORY_NAME:-nova-file-api}"
export NOVA_DEPLOY_SERVICE_NAME="${NOVA_DEPLOY_SERVICE_NAME:-nova-file-api}"
export SIGNER_NAME="${SIGNER_NAME:?Set SIGNER_NAME}"
export SIGNER_EMAIL="${SIGNER_EMAIL:?Set SIGNER_EMAIL}"
export NOVA_ARTIFACT_BUCKET_NAME="${NOVA_ARTIFACT_BUCKET_NAME:?Set NOVA_ARTIFACT_BUCKET_NAME}"
export GITHUB_OIDC_PROVIDER_ARN="${GITHUB_OIDC_PROVIDER_ARN:?Set GITHUB_OIDC_PROVIDER_ARN}"

if [ -z "${AWS_ACCOUNT_ID:-}" ]; then
  AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
  export AWS_ACCOUNT_ID
fi

export ECR_REPOSITORY_URI="${ECR_REPOSITORY_URI:-${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY_NAME}}"
export ECR_REPOSITORY_ARN="${ECR_REPOSITORY_ARN:-arn:aws:ecr:${AWS_REGION}:${AWS_ACCOUNT_ID}:repository/${ECR_REPOSITORY_NAME}}"

if [ "${CODEARTIFACT_STAGING_REPOSITORY}" = "${CODEARTIFACT_PROD_REPOSITORY}" ]; then
  echo "CODEARTIFACT_STAGING_REPOSITORY and CODEARTIFACT_PROD_REPOSITORY must differ." >&2
  exit 1
fi
```

Explicit targeting guardrail:

- `GITHUB_OWNER` and `GITHUB_REPO` must name the intended production
  repository before Step 3.
- `./scripts/release/day-0-operator-command-pack.sh` does not infer the target
  repo from `origin` or any other checkout metadata.

Required pre-check before Step 3 (replace `nova-file-api` if overridden via
`NOVA_DEPLOY_SERVICE_NAME`):

```bash
aws ssm get-parameter --region "${AWS_REGION}" --name "/nova/dev/${NOVA_DEPLOY_SERVICE_NAME}/base-url"
aws ssm get-parameter --region "${AWS_REGION}" --name "/nova/prod/${NOVA_DEPLOY_SERVICE_NAME}/base-url"
```

Ownership guardrail:

- Base-url parameters are owned by the canonical stack pair
  `${PROJECT}-${APPLICATION}-dev-service-base-url` and
  `${PROJECT}-${APPLICATION}-prod-service-base-url`.
- Do not create alternate stack names that manage the same SSM parameter paths.

### Step 2: Bootstrap foundation stack first

If `${NOVA_ARTIFACT_BUCKET_NAME}` already exists, pass it as
`ExistingArtifactBucketName`. If it does not exist yet, set
`ExistingArtifactBucketName=""` and pass it as `ArtifactBucketName`.

Artifact bucket retention baseline:

- If the foundation stack creates the bucket, `nova-foundation.yml` applies the
  lifecycle baseline automatically.
- If the bucket already exists and you pass `ExistingArtifactBucketName`, apply
  equivalent lifecycle controls directly on the bucket:
  current-object expiration after 30 days, noncurrent-version expiration after
  30 days, and incomplete multipart abort after 7 days.

```bash
if aws s3api head-bucket --bucket "${NOVA_ARTIFACT_BUCKET_NAME}" >/dev/null 2>&1; then
  FOUNDATION_BUCKET_ARGS=(
    ExistingArtifactBucketName="${NOVA_ARTIFACT_BUCKET_NAME}"
    ArtifactBucketName=""
  )
else
  FOUNDATION_BUCKET_ARGS=(
    ExistingArtifactBucketName=""
    ArtifactBucketName="${NOVA_ARTIFACT_BUCKET_NAME}"
  )
fi

aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-foundation" \
  --template-file infra/nova/nova-foundation.yml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Project="${PROJECT}" \
    Application="${APPLICATION}" \
    "${FOUNDATION_BUCKET_ARGS[@]}" \
    CodeArtifactDomainName="${CODEARTIFACT_DOMAIN}" \
    EcrRepositoryArn="${ECR_REPOSITORY_ARN}" \
    EcrRepositoryName="${ECR_REPOSITORY_NAME}" \
    EcrRepositoryUri="${ECR_REPOSITORY_URI}" \
    ExistingConnectionArn="${EXISTING_CONNECTION_ARN}"
```

### Step 3: Run command pack

```bash
./scripts/release/day-0-operator-command-pack.sh
```

### Step 4: Validate stack outputs

```bash
aws cloudformation describe-stacks --region "${AWS_REGION}" --stack-name "${PROJECT}-${APPLICATION}-nova-foundation" --query 'Stacks[0].Outputs'
aws cloudformation describe-stacks --region "${AWS_REGION}" --stack-name "${PROJECT}-${APPLICATION}-nova-iam-roles" --query 'Stacks[0].Outputs'
aws cloudformation describe-stacks --region "${AWS_REGION}" --stack-name "${PROJECT}-${APPLICATION}-nova-ci-cd" --query 'Stacks[0].Outputs'
```

### Step 5: Verify GitHub wiring is complete

```bash
required_secrets=(RELEASE_SIGNING_SECRET_ID RELEASE_AWS_ROLE_ARN)
required_vars=(AWS_REGION CODEARTIFACT_DOMAIN CODEARTIFACT_STAGING_REPOSITORY CODEARTIFACT_PROD_REPOSITORY)

existing_secrets="$(gh secret list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --json name -q '.[].name')"
existing_vars="$(gh variable list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --json name -q '.[].name')"

for key in "${required_secrets[@]}"; do
  grep -qx "${key}" <<< "${existing_secrets}" || { echo "Missing secret: ${key}"; exit 1; }
done
for key in "${required_vars[@]}"; do
  grep -qx "${key}" <<< "${existing_vars}" || { echo "Missing variable: ${key}"; exit 1; }
done

echo "All required GitHub secrets/variables are present."
```

### Step 6: Trigger and verify release workflows/pipeline progression

```bash
export CODEPIPELINE_NAME="$(aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-ci-cd" \
  --query "Stacks[0].Outputs[?OutputKey=='PipelineName'].OutputValue | [0]" \
  --output text)"

gh workflow run "Nova Release Plan" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main
PLAN_RUN_ID="$(gh run list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --workflow "Nova Release Plan" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "${PLAN_RUN_ID}" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --exit-status

gh workflow run "Nova Release Apply" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main
APPLY_RUN_ID="$(gh run list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --workflow "Nova Release Apply" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "${APPLY_RUN_ID}" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --exit-status

gh workflow run "Publish Packages" \
  --repo "${GITHUB_OWNER}/${GITHUB_REPO}" \
  --ref main \
  -f release_apply_run_id="${APPLY_RUN_ID}"
PUBLISH_RUN_ID="$(gh run list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --workflow "Publish Packages" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "${PUBLISH_RUN_ID}" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --exit-status

gh workflow run "Deploy Dev" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main -f pipeline_name="${CODEPIPELINE_NAME}"
DEPLOY_RUN_ID="$(gh run list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --workflow "Deploy Dev" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "${DEPLOY_RUN_ID}" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --exit-status

aws codepipeline get-pipeline-state --region "${AWS_REGION}" --name "${CODEPIPELINE_NAME}"
```

`Publish Packages` is the canonical manual staging publish workflow for Python,
TypeScript/npm, and R artifacts. `Promote Prod` is the canonical manual prod
promotion workflow for those staged, gate-validated artifacts. Capture the
successful `APPLY_RUN_ID` and staged-publish evidence, then run `Promote Prod`
with:

- `pipeline_name`
- `manifest_sha256`
- `changed_units_json`
- `changed_units_sha256`
- `version_plan_json`
- `version_plan_sha256`
- `promotion_candidates_json`
- `promotion_candidates_sha256`

### Step 7: Return to idle cost posture after release work

When release work is complete and you do not need the AWS promotion control
plane live, delete the two idle-cost stacks:

```bash
aws cloudformation delete-stack \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-ci-cd"
aws cloudformation wait stack-delete-complete \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-ci-cd"

aws cloudformation delete-stack \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-codebuild-release"
aws cloudformation wait stack-delete-complete \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-codebuild-release"
```

Dormant-state reminder:

- The low-cost Nova shell keeps `${PROJECT}-${APPLICATION}-nova-foundation`,
  `${PROJECT}-${APPLICATION}-nova-iam-roles`, and the digest marker stacks
  `${PROJECT}-${APPLICATION}-nova-dev` / `${PROJECT}-${APPLICATION}-nova-prod`.
- Do not keep `nova-ci-cd`, `nova-codebuild-release`, runtime stacks, or
  base-url marker stacks deployed when the runtime and release control plane
  are intentionally dormant.

Dormant-state verification:

```bash
aws codeconnections list-connections --region "${AWS_REGION}"

aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-foundation" \
  --query 'Stacks[0].Parameters[?ParameterKey==`ExistingConnectionArn`].ParameterValue | [0]' \
  --output text

aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-iam-roles" \
  --query 'Stacks[0].Parameters[?ParameterKey==`ExistingConnectionArn`].ParameterValue | [0]' \
  --output text

aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-prod" \
  --query 'Stacks[0].Outputs'

aws codebuild list-projects --region "${AWS_REGION}"
aws codepipeline list-pipelines --region "${AWS_REGION}"
aws ecs list-clusters --region "${AWS_REGION}"
aws ssm get-parameter --region "${AWS_REGION}" --name "/nova/dev/${NOVA_DEPLOY_SERVICE_NAME}/image-digest"
aws ssm get-parameter --region "${AWS_REGION}" --name "/nova/prod/${NOVA_DEPLOY_SERVICE_NAME}/image-digest"
```

Expected dormant-state result:

- only the current `arn:aws:codeconnections:*` connection ARN remains for Nova
- `nova-foundation`, `nova-iam-roles`, `nova-dev`, and `nova-prod` exist
- CodeBuild and CodePipeline control-plane resources remain deleted
- runtime/base-url stacks remain deleted
- both digest parameters remain CloudFormation-backed

Recreate them later with `./scripts/release/day-0-operator-command-pack.sh`.

Runbook: `docs/runbooks/release/release-promotion-dev-to-prod.md`

Pipeline dashboard:
`https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows`

## Acceptance checks

1. Release signing and workflow auth are valid.
2. Pipeline completes Dev -> ManualApproval -> Prod in order.
3. `FILE_IMAGE_DIGEST` continuity is preserved Dev to Prod.
4. Durable promotion evidence (workflow run URLs, digest continuity, approval
   record) is captured per [`release-policy.md`](../release/release-policy.md) §6.

## References

- [runbooks README](../../runbooks/README.md)
- [governance-lock-and-branch-protection.md](../release/governance-lock-and-branch-protection.md)
- [troubleshooting-and-break-glass.md](../release/troubleshooting-and-break-glass.md)
