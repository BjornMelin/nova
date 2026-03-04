# Config Values Reference Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-03

## Purpose

Provide one reference for all values needed to provision runtime stacks,
configure CI/CD stacks, and operate Nova release automation.

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
- `AWS_ACCOUNT_ID`
- `SIGNER_NAME`
- `SIGNER_EMAIL`
- `CODEARTIFACT_DOMAIN_NAME`
- `CODEARTIFACT_REPOSITORY_NAME`
- `ECR_REPOSITORY_ARN`

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

`NOVA_DEPLOY_DEV_STACK_NAME` / `NOVA_DEPLOY_PROD_STACK_NAME` are digest marker
stack names used by pipeline deploy actions (`infra/nova/deploy/image-digest-ssm.yml`),
not the runtime ECS service stack names.

## Runtime stack parameter contract

Capture and manage these runtime values per environment before CI/CD deploy:

- `VPC_ID`
- `SUBNET_IDS`
- `ALB_HOSTED_ZONE_NAME`
- `ALB_DNS_NAME`
- `ALB_NAME`
- `ALB_LOG_BUCKET`
- `ALB_INGRESS_PREFIX_LIST_ID` or `ALB_INGRESS_CIDR` or
  `ALB_INGRESS_SOURCE_SG_ID` (exactly one)
- `ECS_CLUSTER_NAME`
- `SERVICE_NAME`
- `SERVICE_DNS`
- `TASK_ROLE_ARN`
- `DOCKER_REPOSITORY_NAME`
- `DOCKER_IMAGE_TAG`
- `OWNER_TAG`
- `ALARM_ACTION_ARN`

See:
`deploy-runtime-cloudformation-environments-guide.md`

## CloudFormation stack names and outputs

Default stack names:

- `${project}-${application}-nova-foundation`
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


## Promote-prod workflow dispatch inputs

`promote-prod.yml` requires these runtime inputs:

- `pipeline_name`
- `manifest_sha256`
- `changed_units_json`
- `version_plan_json`
- `promotion_candidates_json`

Source all JSON payload inputs from `publish-packages.yml` gate artifacts.

## Endpoint and validation contract

Validation URLs:

- `${DEV_BASE_URL}/v1/transfers/uploads/initiate`
- `${DEV_BASE_URL}/metrics/summary`
- `${DEV_BASE_URL}/v1/jobs`
- `${DEV_BASE_URL}/v1/health/live`
- `${DEV_BASE_URL}/v1/health/ready`
- `${DEV_BASE_URL}/v1/capabilities`
- `${PROD_BASE_URL}/v1/transfers/uploads/initiate`
- `${PROD_BASE_URL}/metrics/summary`
- `${PROD_BASE_URL}/v1/jobs`
- `${PROD_BASE_URL}/v1/health/live`
- `${PROD_BASE_URL}/v1/health/ready`
- `${PROD_BASE_URL}/v1/capabilities`

Route namespace policy:

- Canonical consumer capability namespace is `/v1/*`.
- Release validation inputs MUST use canonical `/v1/*` routes and
  `/metrics/summary` only.
- Non-canonical route literals MUST NOT appear in validation commands.

## References

- Publish packages workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/publish-packages.yml>
- Build/publish image workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/build-and-publish-image.yml>
- Promote prod workflow:
  <https://github.com/3M-Cloud/nova/blob/main/.github/workflows/promote-prod.yml>
- CodeBuild environment variable types:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-codebuild-project-environmentvariable.html>
