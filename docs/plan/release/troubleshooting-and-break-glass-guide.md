# Troubleshooting and Break-Glass Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

Provide failure diagnostics and emergency command paths for Nova CI/CD
provisioning and release promotion.

## Prerequisites

1. AWS CLI v2 configured with incident-response permissions.
2. CloudFormation, CodePipeline, CodeBuild, and IAM read permissions.
3. Access to both repository workflow run histories.

### Before running commands

Use these setup guides for variable definitions and sourcing:

- [day-0-operator-checklist.md](day-0-operator-checklist.md)
- [aws-oidc-and-iam-role-setup-guide.md](aws-oidc-and-iam-role-setup-guide.md)
- [config-values-reference-guide.md](config-values-reference-guide.md)

Primary variable sources:

- `${PROJECT}` and `${APPLICATION}`: deployment naming defaults from day-0
  checklist/config guide.
- `${AWS_REGION}`: operator/runtime environment and GitHub `AWS_REGION` variable.
- `${CONNECTION_ARN}`: CodePipeline stack output `ConnectionArn`.
- `${RELEASE_SIGNING_SECRET_ID}`: GitHub secret set from Secrets Manager
  `${SECRET_NAME}`.
- `${RELEASE_BUILD_PROJECT_NAME}`: CodeBuild project name from stack outputs or
  configured overrides.
- `${DEPLOY_STACK_NAME}`: target CloudFormation deployment stack name from
  environment-specific config.

## Quick failure matrix

### `Apply Release Plan` cannot assume AWS role

Likely causes:

- bad `RELEASE_AWS_ROLE_ARN`
- OIDC trust `sub` mismatch with branch/repo
- missing `id-token: write` workflow permission

Commands:

```bash
aws iam get-role --role-name "${PROJECT}-${APPLICATION}-github-oidc-release-role"
aws iam list-attached-role-policies --role-name "${PROJECT}-${APPLICATION}-github-oidc-release-role"
```

### Secrets Manager retrieval fails

Likely causes:

- wrong `RELEASE_SIGNING_SECRET_ID`
- secret policy denies role access

Commands:

```bash
aws secretsmanager get-secret-value \
  --region "${AWS_REGION}" \
  --secret-id "${RELEASE_SIGNING_SECRET_ID}"
```

### CodeConnections stuck in `PENDING`

Likely causes:

- no console authorization handshake completed

Commands:

```bash
aws codeconnections get-connection \
  --region "${AWS_REGION}" \
  --connection-arn "${CONNECTION_ARN}"
```

### Build stage fails on ECR/CodeArtifact

Likely causes:

- missing CodeBuild env vars
- insufficient IAM for ECR push or CodeArtifact publish

Commands:

```bash
aws codebuild batch-get-projects --names "${RELEASE_BUILD_PROJECT_NAME}"
aws logs tail "/aws/codebuild/${RELEASE_BUILD_PROJECT_NAME}" --follow
```

### Deploy stages fail on CloudFormation

Likely causes:

- wrong template artifact path
- missing deploy stack parameter names
- cfn execution role missing `iam:PassRole` or ECS permissions

Commands:

```bash
aws cloudformation describe-stack-events \
  --region "${AWS_REGION}" \
  --stack-name "${DEPLOY_STACK_NAME}"
```

## Break-glass CLI deployment sequence

If GitHub action path is unavailable, deploy stacks directly:

```bash
aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-iam-roles" \
  --template-file "${NOVA_REPO_ROOT}/infra/nova/nova-iam-roles.yml" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    Project="${PROJECT}" \
    Application="${APPLICATION}" \
    RepositoryOwner="${GITHUB_OWNER}" \
    RepositoryName="${GITHUB_REPO}" \
    MainBranchName="main" \
    GitHubOidcProviderArn="${GITHUB_OIDC_PROVIDER_ARN}" \
    ReleaseSigningSecretArn="${RELEASE_SIGNING_SECRET_ARN}" \
    ArtifactBucketName="${NOVA_ARTIFACT_BUCKET_NAME}" \
    CodeArtifactDomainName="${NOVA_CODEARTIFACT_DOMAIN_NAME}" \
    CodeArtifactRepositoryName="${NOVA_CODEARTIFACT_REPOSITORY_NAME}" \
    EcrRepositoryArn="${NOVA_ECR_REPOSITORY_ARN}"
```

Use equivalent `aws cloudformation deploy` commands for:

- `nova-codebuild-release.yml`
- `nova-ci-cd.yml`

with parameter sets from:
`infra/nova/*.yml` templates and `scripts/release/day-0-operator-command-pack.sh` in this repository.

## Post-incident recording

Always record:

1. UTC timestamp
2. incident summary
3. root cause
4. remediation commands run
5. prevention action

Store evidence in:

- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- `docs/plan/PLAN.md`
- `FINAL-PLAN.md`

## References

- AWS CloudFormation deploy API:
  <https://docs.aws.amazon.com/cli/latest/reference/cloudformation/deploy.html>
- AWS CloudFormation describe-stack-events API:
  <https://docs.aws.amazon.com/cli/latest/reference/cloudformation/describe-stack-events.html>
- AWS CodeBuild batch-get-projects API:
  <https://docs.aws.amazon.com/cli/latest/reference/codebuild/batch-get-projects.html>
- AWS logs tail API:
  <https://docs.aws.amazon.com/cli/latest/reference/logs/tail.html>
