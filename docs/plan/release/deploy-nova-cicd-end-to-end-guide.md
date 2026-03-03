# Deploy Nova CI/CD End-to-End Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

Provide a complete deploy sequence for Nova CI/CD resources and first release
execution.

## Prerequisites

1. `nova` repo access and workflow execution permissions.
2. AWS credentials configured for stack deployment account.
3. Release signing secret created in Secrets Manager.
4. GitHub OIDC provider and trust role setup completed.
5. `nova` repository admin rights for secrets/variables configuration.

## Deployment model

Primary path:

1. Deploy infrastructure from `nova/infra/nova/**` templates.
2. Configure `nova` repository secrets/vars.
3. Activate CodeConnections.
4. Run release workflows and validate AWS promotion.

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

## Step 1: set deployment values

Export the required values for the Nova operator command pack:

- `GITHUB_OIDC_PROVIDER_ARN`
- `SECRET_NAME` / `RELEASE_SIGNING_SECRET_ARN`
- `NOVA_ARTIFACT_BUCKET_NAME`
- `ECR_REPOSITORY_URI` and `ECR_REPOSITORY_NAME`
- `NOVA_DEV_SERVICE_BASE_URL`
- `NOVA_PROD_SERVICE_BASE_URL`
- optional: `EXISTING_CONNECTION_ARN`

Reference details:
[config-values-reference-guide.md](config-values-reference-guide.md)

## Step 2: deploy CI/CD stacks from nova

Run the operator command pack:

```bash
./scripts/release/day-0-operator-command-pack.sh
```

## Step 3: capture stack outputs

```bash
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

## Step 4: configure GitHub repo secrets and vars

Run setup from:
[github-actions-secrets-and-vars-setup-guide.md](github-actions-secrets-and-vars-setup-guide.md)

## Step 5: activate CodeConnections

Run activation checks from:
[codeconnections-activation-and-validation-guide.md](codeconnections-activation-and-validation-guide.md)

## Step 6: run build/package/deploy workflows

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

## Step 7: validate pipeline promotion path

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

## References

- CodePipeline get-pipeline-state API:
  <https://docs.aws.amazon.com/cli/latest/reference/codepipeline/get-pipeline-state.html>
- GitHub workflow dispatch with CLI:
  <https://cli.github.com/manual/gh_workflow_run>
