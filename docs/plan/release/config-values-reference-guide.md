# Config Values Reference Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

Provide one reference for all values needed to provision, configure, and operate
Nova CI/CD.

## Prerequisites

1. Access to `3M-Cloud/nova` repository.
2. Ability to inspect deployed CloudFormation stack outputs.
3. Existing release stack deployment or planned stack parameter set.

## GitHub repository secrets and vars (`3M-Cloud/nova`)

### Required secrets

- `RELEASE_SIGNING_SECRET_ID`
  - value: Secrets Manager secret ID or ARN for release signing JSON
- `RELEASE_AWS_ROLE_ARN`
  - value: IAM role ARN output `GitHubOIDCReleaseRoleArn`

### Required vars

- `AWS_REGION`
  - default: `us-east-1`

## Nova operator command-pack environment keys

Required keys:

- `GITHUB_OIDC_PROVIDER_ARN`
- `SECRET_NAME` (or resolved `RELEASE_SIGNING_SECRET_ARN`)
- `NOVA_ARTIFACT_BUCKET_NAME`
- `NOVA_DEV_SERVICE_BASE_URL`
- `NOVA_PROD_SERVICE_BASE_URL`

Required ECR targeting:

- `ECR_REPOSITORY_URI`
- `ECR_REPOSITORY_NAME`

Optional keys:

- `EXISTING_CONNECTION_ARN`
- `NOVA_MANUAL_APPROVAL_TOPIC_ARN`
- `CONNECTION_NAME`
- `NOVA_RELEASE_BUILD_PROJECT_NAME`
- `NOVA_DEPLOY_VALIDATE_PROJECT_NAME`
- `NOVA_DEPLOY_SERVICE_NAME`
- `NOVA_DEPLOY_DEV_STACK_NAME`
- `NOVA_DEPLOY_PROD_STACK_NAME`

## CloudFormation stack names and outputs

Default stack names:

- `${project}-${application}-nova-iam-roles`
- `${project}-${application}-nova-codebuild-release`
- `${project}-${application}-nova-ci-cd`

Critical outputs:

- `GitHubOIDCReleaseRoleArn`
- `PipelineName`
- `ConnectionArn`

## CodeBuild environment contract

Release build project requires:

- `CODEARTIFACT_DOMAIN`
- `CODEARTIFACT_STAGING_REPOSITORY`
- `CODEARTIFACT_PROD_REPOSITORY`
- `ECR_REPOSITORY_URI` or `ECR_REPOSITORY_NAME`
- `DOCKERFILE_PATH`
- `DOCKER_BUILD_CONTEXT`

Exported variables:

- `IMAGE_DIGEST`
- `PUBLISHED_PACKAGES`
- `RELEASE_MANIFEST_SHA256`
- `CHANGED_UNITS`

Reference file:
`buildspecs/buildspec-release.yml`

## Endpoint and validation contract

Validation URLs:

- `${DEV_BASE_URL}/healthz`
- `${DEV_BASE_URL}/readyz`
- `${DEV_BASE_URL}/metrics/summary`
- `${PROD_BASE_URL}/healthz`
- `${PROD_BASE_URL}/readyz`
- `${PROD_BASE_URL}/metrics/summary`

## References

- Publish packages workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/publish-packages.yml>
- Build/publish image workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/build-and-publish-image.yml>
- Promote prod workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/promote-prod.yml>
- CodeBuild environment variable types:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-codebuild-project-environmentvariable.html>
