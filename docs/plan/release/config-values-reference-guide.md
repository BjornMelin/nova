# Config Values Reference Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

Provide one reference for all values needed to provision, configure, and operate
Nova CI/CD.

## Prerequisites

1. Access to both repositories:
   - `3M-Cloud/nova`
   - `3M-Cloud/container-craft`
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

## container-craft service config keys for `deploy-nova-cicd`

Required keys:

- `github_oidc_provider_arn`
- `release_signing_secret_arn`
- `nova_artifact_bucket_name`
- `nova_dev_service_base_url`
- `nova_prod_service_base_url`

Required ECR targeting (at least one):

- `nova_ecr_repository_uri`
- `nova_ecr_repository_name`

Optional keys:

- `nova_existing_connection_arn`
- `nova_manual_approval_topic_arn`
- `nova_connection_name`
- `nova_release_build_project_name`
- `nova_deploy_validate_project_name`
- `nova_deploy_service_name`
- `nova_deploy_dev_stack_name`
- `nova_deploy_prod_stack_name`

Defaults live in:
`/home/bjorn/repos/work/infra-stack/container-craft/src/container-craft/settings/service.yml`

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
- `CODEARTIFACT_REPOSITORY`
- `ECR_REPOSITORY_URI` or `ECR_REPOSITORY_NAME`
- `DOCKERFILE_PATH`
- `DOCKER_BUILD_CONTEXT`

Exported variables:

- `IMAGE_DIGEST`
- `PUBLISHED_PACKAGES`
- `RELEASE_MANIFEST_SHA256`
- `CHANGED_UNITS`

Reference file:
`/home/bjorn/repos/work/infra-stack/nova/buildspecs/buildspec-release.yml`

## Endpoint and validation contract

Validation URLs:

- `${DEV_BASE_URL}/healthz`
- `${DEV_BASE_URL}/readyz`
- `${DEV_BASE_URL}/metrics/summary`
- `${PROD_BASE_URL}/healthz`
- `${PROD_BASE_URL}/readyz`
- `${PROD_BASE_URL}/metrics/summary`

## References

- Release apply workflow:
  <https://github.com/BjornMelin/nova/blob/main/.github/workflows/release-apply.yml>
- CodeBuild environment variable types:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-codebuild-project-environmentvariable.html>
