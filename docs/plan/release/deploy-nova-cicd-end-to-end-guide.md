# Deploy Nova CI/CD End-to-End Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-17

## Purpose

Provide a complete deploy sequence for Nova CI/CD resources and first release
execution after runtime environments are provisioned, with the governing
authority chain cited for operators.

## References

- [release-authority-chain.md](release-authority-chain.md)

## Prerequisites

1. `nova` repo access and workflow execution permissions.
2. AWS credentials configured for stack deployment account.
3. Release signing secret created in Secrets Manager.
4. GitHub OIDC provider and trust role setup completed.
5. `nova` repository admin rights for secrets/variables configuration.
6. Runtime stacks are already deployed for `dev` and `prod` per:
   [deploy-runtime-cloudformation-environments-guide.md](deploy-runtime-cloudformation-environments-guide.md)
7. Canonical base URL SSM parameters exist for both environments:
   `/nova/dev/{service}/base-url` and `/nova/prod/{service}/base-url`.
8. Canonical base-url marker stacks are reserved for CI control-plane ownership:
   `${PROJECT}-${APPLICATION}-dev-service-base-url` and
   `${PROJECT}-${APPLICATION}-prod-service-base-url`.

## Deployment model

Primary path:

1. Deploy runtime stacks for both environments (`infra/runtime/**`).
2. Deploy foundation infrastructure from `infra/nova/nova-foundation.yml`.
3. Deploy remaining CI/CD infrastructure from `infra/nova/**` templates.
4. Configure `nova` repository secrets/vars.
5. Activate CodeConnections.
6. Run release workflows and validate AWS promotion.
7. Delete the release-control stacks when the environment returns to an idle
   development posture.

Fallback path:

- use direct AWS CLI/CloudFormation commands documented in
  [troubleshooting-and-break-glass-guide.md](troubleshooting-and-break-glass-guide.md)

## Inputs checklist

- `${AWS_REGION}`
- `${PROJECT}` default `nova`
- `${APPLICATION}` default `ci`
- `${NOVA_REPO_ROOT}` local checkout path for the `nova` repository
- `${GITHUB_OWNER}` default `3M-Cloud`
- `${GITHUB_REPO}` default `nova`
- `${AWS_ACCOUNT_ID}`
- `${SIGNER_NAME}`
- `${SIGNER_EMAIL}`
- `${CODEARTIFACT_DOMAIN_NAME}`
- `${CODEARTIFACT_REPOSITORY_NAME}` (optional fallback for staging default)
- `${CODEARTIFACT_STAGING_REPOSITORY}`
- `${CODEARTIFACT_PROD_REPOSITORY}` (must differ from staging)
- `${ECR_REPOSITORY_ARN}`
- `${ECR_REPOSITORY_NAME}`
- `${ECR_REPOSITORY_URI}`
- `${NOVA_ARTIFACT_BUCKET_NAME}`
- `${NOVA_DEPLOY_SERVICE_NAME}` (optional, default `nova-file-api`)
- `${GITHUB_OIDC_PROVIDER_ARN}`
- `${SECRET_NAME}` or `${RELEASE_SIGNING_SECRET_ARN}`
- `${DEV_BASE_URL}` example `https://nova-file-api.dev.example.com`
- `${PROD_BASE_URL}` example `https://nova-file-api.example.com`
- `${EXISTING_CONNECTION_ARN}` (optional)
- `${NOVA_MANUAL_APPROVAL_TOPIC_ARN}` (optional)

## Step 1: set deployment values

Export the required values for the Nova operator command pack:

- `AWS_REGION`, `PROJECT`, `APPLICATION`, and `NOVA_DEPLOY_SERVICE_NAME`
- `DEV_BASE_URL` and `PROD_BASE_URL`
- `GITHUB_OIDC_PROVIDER_ARN`
- `SECRET_NAME` / `RELEASE_SIGNING_SECRET_ARN`
- `NOVA_ARTIFACT_BUCKET_NAME`
- `ECR_REPOSITORY_URI` and `ECR_REPOSITORY_NAME`
- `CODEARTIFACT_STAGING_REPOSITORY` (or `CODEARTIFACT_REPOSITORY_NAME` fallback)
- `CODEARTIFACT_PROD_REPOSITORY`
- optional: `EXISTING_CONNECTION_ARN`
- optional: `NOVA_MANUAL_APPROVAL_TOPIC_ARN`

Example exports:

```bash
export AWS_REGION="${AWS_REGION:-us-west-2}"
export PROJECT="${PROJECT:-nova}"
export APPLICATION="${APPLICATION:-ci}"
export NOVA_DEPLOY_SERVICE_NAME="${NOVA_DEPLOY_SERVICE_NAME:-nova-file-api}"
export DEV_BASE_URL="${DEV_BASE_URL:?set to the dev runtime base URL, for example https://nova-file-api.dev.example.com}"
export PROD_BASE_URL="${PROD_BASE_URL:?set to the prod runtime base URL, for example https://nova-file-api.example.com}"
```

Reference details:
[config-values-reference-guide.md](config-values-reference-guide.md)

### Step 1a: persist canonical service base URLs in SSM

Use the CI control-plane stack names as the only owners of these parameter
paths. Do not deploy alternate stack names that manage the same
`/nova/{env}/{service}/base-url` resources.

```bash
aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-dev-service-base-url" \
  --template-file infra/nova/deploy/service-base-url-ssm.yml \
  --parameter-overrides \
    Environment=dev \
    ServiceName="${NOVA_DEPLOY_SERVICE_NAME:-nova-file-api}" \
    ServiceBaseUrl="${DEV_BASE_URL}"

aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-prod-service-base-url" \
  --template-file infra/nova/deploy/service-base-url-ssm.yml \
  --parameter-overrides \
    Environment=prod \
    ServiceName="${NOVA_DEPLOY_SERVICE_NAME:-nova-file-api}" \
    ServiceBaseUrl="${PROD_BASE_URL}"
```

Set and validate promotion repositories:

```bash
export CODEARTIFACT_REPOSITORY_NAME="${CODEARTIFACT_REPOSITORY_NAME:-galaxypy}"
export CODEARTIFACT_STAGING_REPOSITORY="${CODEARTIFACT_STAGING_REPOSITORY:-${CODEARTIFACT_REPOSITORY_NAME}}"
export CODEARTIFACT_PROD_REPOSITORY="${CODEARTIFACT_PROD_REPOSITORY:?required}"

if [ "${CODEARTIFACT_STAGING_REPOSITORY}" = "${CODEARTIFACT_PROD_REPOSITORY}" ]; then
  echo "CODEARTIFACT_STAGING_REPOSITORY and CODEARTIFACT_PROD_REPOSITORY must differ." >&2
  exit 1
fi
```

## Step 2: deploy foundation stack from nova (manual option)

Choose one of the two flows below:

- Option A: run Step 2 manually to deploy `${PROJECT}-${APPLICATION}-nova-foundation`, then continue to Step 3.
- Option B: skip manual Step 2 and rely on Step 3; the command pack deploy will create `${PROJECT}-${APPLICATION}-nova-foundation` as its first action.

If you run Step 2 manually, the later command pack in Step 3 will still re-apply
`${PROJECT}-${APPLICATION}-nova-foundation` using the same parameter values; ensure
the values match for idempotent behavior.

If `${NOVA_ARTIFACT_BUCKET_NAME}` already exists, pass it as
`ExistingArtifactBucketName`. If it does not exist yet, set
`ExistingArtifactBucketName=""` and pass it as `ArtifactBucketName`.

If you import an existing artifact bucket with `ExistingArtifactBucketName`,
the stack does not own that bucket resource. Apply the same lifecycle baseline
directly on the bucket:

- expire current objects after 30 days
- expire noncurrent versions after 30 days
- abort incomplete multipart uploads after 7 days

If the artifact bucket already exists:

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
    CodeArtifactDomainName="${CODEARTIFACT_DOMAIN_NAME}" \
    CodeArtifactRepositoryName="${CODEARTIFACT_STAGING_REPOSITORY}" \
    EcrRepositoryArn="${ECR_REPOSITORY_ARN}" \
    EcrRepositoryName="${ECR_REPOSITORY_NAME}" \
    EcrRepositoryUri="${ECR_REPOSITORY_URI}" \
    ExistingConnectionArn="${EXISTING_CONNECTION_ARN:-}"
```

If the artifact bucket does not yet exist:

```bash
aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-foundation" \
  --template-file infra/nova/nova-foundation.yml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Project="${PROJECT}" \
    Application="${APPLICATION}" \
    ExistingArtifactBucketName="" \
    ArtifactBucketName="${NOVA_ARTIFACT_BUCKET_NAME}" \
    CodeArtifactDomainName="${CODEARTIFACT_DOMAIN_NAME}" \
    CodeArtifactRepositoryName="${CODEARTIFACT_STAGING_REPOSITORY}" \
    EcrRepositoryArn="${ECR_REPOSITORY_ARN}" \
    EcrRepositoryName="${ECR_REPOSITORY_NAME}" \
    EcrRepositoryUri="${ECR_REPOSITORY_URI}" \
    ExistingConnectionArn="${EXISTING_CONNECTION_ARN:-}"
```

`CodeArtifactRepositoryName` maps to staged publish storage; promotion to prod is
controlled by IAM parameters:
`CodeArtifactPromotionSourceRepositoryName` and
`CodeArtifactPromotionDestinationRepositoryName`.

## Step 3: deploy CI/CD stacks from nova

Run the operator command pack:

```bash
./scripts/release/day-0-operator-command-pack.sh
```

If you ran Step 2 manually, this is an intentional re-apply for idempotency:

- `${PROJECT}-${APPLICATION}-nova-foundation` is re-deployed first with the same
  parameter values passed in Step 2.

The command pack deploys stacks in this order:

1. `${PROJECT}-${APPLICATION}-nova-foundation`
2. `${PROJECT}-${APPLICATION}-nova-iam-roles`
3. `${PROJECT}-${APPLICATION}-nova-codebuild-release`
4. `${PROJECT}-${APPLICATION}-nova-ci-cd`

## Step 4: capture stack outputs

```bash
aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-foundation" \
  --query 'Stacks[0].Outputs'

aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-iam-roles" \
  --query 'Stacks[0].Outputs'

aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-ci-cd" \
  --query 'Stacks[0].Outputs'
```

Record:

- `GitHubOIDCReleaseRoleArn`
- `PipelineName`
- `ConnectionArn`
- `ManualApprovalTopicArn`

## Step 5: configure GitHub repo secrets and vars

Run setup from:
[github-actions-secrets-and-vars-setup-guide.md](github-actions-secrets-and-vars-setup-guide.md)

## Step 6: activate CodeConnections

Run activation checks from:
[codeconnections-activation-and-validation-guide.md](codeconnections-activation-and-validation-guide.md)

## Step 7: run build/package/deploy workflows

```bash
export CODEPIPELINE_NAME="$(aws cloudformation describe-stacks --region "${AWS_REGION}" --stack-name "${PROJECT}-${APPLICATION}-nova-ci-cd" --query "Stacks[0].Outputs[?OutputKey=='PipelineName'].OutputValue | [0]" --output text)"

gh workflow run "Nova Release Plan" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main
PLAN_RUN_ID="$(gh run list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --workflow "Nova Release Plan" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "${PLAN_RUN_ID}" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --exit-status

gh workflow run "Nova Release Apply" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main
APPLY_RUN_ID="$(gh run list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --workflow "Nova Release Apply" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "${APPLY_RUN_ID}" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --exit-status

gh workflow run "Deploy Dev" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main -f pipeline_name="${CODEPIPELINE_NAME}"
DEPLOY_RUN_ID="$(gh run list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --workflow "Deploy Dev" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "${DEPLOY_RUN_ID}" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --exit-status
```

## Step 8: validate pipeline promotion path

Expected stage order:

1. `Source`
2. `Build`
3. `DeployDev`
4. `ValidateDev`
5. `ManualApproval`
6. `DeployProd`
7. `ValidateProd`

Validate with:

```bash
aws codepipeline get-pipeline-state \
  --region "${AWS_REGION}" \
  --name "${CODEPIPELINE_NAME}"
```

## Step 9: return the release control plane to idle

After release validation is complete, delete the control-plane stacks to avoid
idle CodePipeline and CodeBuild spend:

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

Recreate both stacks later by rerunning Step 3.

## References

- CodePipeline get-pipeline-state API:
  <https://docs.aws.amazon.com/cli/latest/reference/codepipeline/get-pipeline-state.html>
- GitHub workflow dispatch with CLI:
  <https://cli.github.com/manual/gh_workflow_run>
