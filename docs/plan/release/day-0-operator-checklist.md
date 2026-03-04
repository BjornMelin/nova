# Day-0 Operator Checklist (Minimal Path)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-03

## Purpose

Run first-time Nova CI/CD provisioning and release promotion using the shortest
safe operator path.

## Prerequisites

1. AWS CLI v2 authenticated.
2. GitHub CLI authenticated.
3. Repository admin access to `${GITHUB_OWNER}/${GITHUB_REPO}` (default: `3M-Cloud/nova`).
4. Required environment values prepared.
5. Runtime stacks already deployed for `dev` and `prod`:
   `deploy-runtime-cloudformation-environments-guide.md`.
6. `jq` and `ssh-keygen` are installed.

## Inputs

- `${AWS_REGION}` (required, e.g., `us-east-1`)
- `${AWS_ACCOUNT_ID}` (required, e.g., `123456789012`)
- `${PROJECT}` (default `nova`)
- `${APPLICATION}` (default `ci`)
- `${GITHUB_OWNER}` (default `3M-Cloud`)
- `${GITHUB_REPO}` (default `nova`)
- `${CONNECTION_ARN}` (required, e.g.,
  `arn:aws:codestar-connections:us-east-1:...:connection/xxxxxxxx`)
- `${CODEARTIFACT_DOMAIN_NAME}` (required)
- `${CODEARTIFACT_REPOSITORY_NAME}` (required)
- `${ECR_REPOSITORY_ARN}` (required)
- `${ECR_REPOSITORY_NAME}` (required)
- `${ECR_REPOSITORY_URI}` (required)
- `${SIGNER_NAME}` (required)
- `${SIGNER_EMAIL}` (required)
- `${NOVA_DEV_SERVICE_BASE_URL}` (required)
- `${NOVA_PROD_SERVICE_BASE_URL}` (required)
- `${NOVA_ARTIFACT_BUCKET_NAME}` (required)

## Step-by-step commands

### Step 1: Export required values

```bash
export AWS_REGION="${AWS_REGION:?Set AWS_REGION}"
export AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
export PROJECT="${PROJECT:-nova}"
export APPLICATION="${APPLICATION:-ci}"
export GITHUB_OWNER="${GITHUB_OWNER:-3M-Cloud}"
export GITHUB_REPO="${GITHUB_REPO:-nova}"
export CONNECTION_ARN="${CONNECTION_ARN:?Set CONNECTION_ARN}"
export CODEARTIFACT_DOMAIN_NAME="${CODEARTIFACT_DOMAIN_NAME:?Set CODEARTIFACT_DOMAIN_NAME}"
export CODEARTIFACT_REPOSITORY_NAME="${CODEARTIFACT_REPOSITORY_NAME:?Set CODEARTIFACT_REPOSITORY_NAME}"
export ECR_REPOSITORY_ARN="${ECR_REPOSITORY_ARN:?Set ECR_REPOSITORY_ARN}"
export ECR_REPOSITORY_NAME="${ECR_REPOSITORY_NAME:?Set ECR_REPOSITORY_NAME}"
export ECR_REPOSITORY_URI="${ECR_REPOSITORY_URI:?Set ECR_REPOSITORY_URI}"
export SIGNER_NAME="${SIGNER_NAME:?Set SIGNER_NAME}"
export SIGNER_EMAIL="${SIGNER_EMAIL:?Set SIGNER_EMAIL}"
export NOVA_ARTIFACT_BUCKET_NAME="${NOVA_ARTIFACT_BUCKET_NAME:?Set NOVA_ARTIFACT_BUCKET_NAME}"
export NOVA_DEV_SERVICE_BASE_URL="${NOVA_DEV_SERVICE_BASE_URL:?Set NOVA_DEV_SERVICE_BASE_URL}"
export NOVA_PROD_SERVICE_BASE_URL="${NOVA_PROD_SERVICE_BASE_URL:?Set NOVA_PROD_SERVICE_BASE_URL}"
```

### Step 2: Bootstrap foundation stack first

If `${NOVA_ARTIFACT_BUCKET_NAME}` already exists, pass it as
`ExistingArtifactBucketName`. If it does not exist yet, set
`ExistingArtifactBucketName=""` and pass it as `ArtifactBucketName`.

```bash
aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-foundation" \
  --template-file infra/nova/nova-foundation.yml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Project="${PROJECT}" \
    Application="${APPLICATION}" \
    ExistingArtifactBucketName="${NOVA_ARTIFACT_BUCKET_NAME}" \
    ArtifactBucketName="" \
    CodeArtifactDomainName="${CODEARTIFACT_DOMAIN_NAME}" \
    CodeArtifactRepositoryName="${CODEARTIFACT_REPOSITORY_NAME}" \
    EcrRepositoryArn="${ECR_REPOSITORY_ARN}" \
    EcrRepositoryName="${ECR_REPOSITORY_NAME}" \
    EcrRepositoryUri="${ECR_REPOSITORY_URI}" \
    ExistingConnectionArn="${CONNECTION_ARN}"
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
required_vars=(AWS_REGION)

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

gh workflow run "Deploy Dev" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main -f pipeline_name="${CODEPIPELINE_NAME}"
DEPLOY_RUN_ID="$(gh run list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --workflow "Deploy Dev" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "${DEPLOY_RUN_ID}" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --exit-status

aws codepipeline get-pipeline-state --region "${AWS_REGION}" --name "${CODEPIPELINE_NAME}"
```

Runbook: `docs/plan/release/release-promotion-dev-to-prod-guide.md`

Pipeline dashboard:
`https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows`

## Acceptance checks

1. Release signing and workflow auth are valid.
2. Pipeline completes Dev -> ManualApproval -> Prod in order.
3. `IMAGE_DIGEST` continuity is preserved Dev to Prod.
4. Evidence links are added to release docs/plan artifacts.

## References

- [runbooks README](../../runbooks/README.md)
- [governance-lock-runbook.md](governance-lock-runbook.md)
- [troubleshooting-and-break-glass-guide.md](troubleshooting-and-break-glass-guide.md)
