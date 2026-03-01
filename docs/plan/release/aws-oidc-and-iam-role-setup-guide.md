# AWS OIDC and IAM Role Setup Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

Configure GitHub OIDC federation and deploy the Nova IAM role stack consumed by
release workflows and AWS pipeline stages.

## Prerequisites

1. AWS CLI configured to target deployment account.
2. Permission to manage IAM providers and roles.
3. `nova` deployment templates available at `infra/nova/**`.

## Inputs

- `${AWS_REGION}` example: `us-east-1`
- `${AWS_ACCOUNT_ID}` example: `123456789012`
- `${PROJECT}` default: `nova`
- `${APPLICATION}` default: `ci`
- `${GITHUB_OWNER}` default: `3M-Cloud`
- `${GITHUB_REPO}` default: `nova`
- `${MAIN_BRANCH}` default: `main`
- `${SIGNING_SECRET_ARN}` from secrets provisioning guide
- `${ARTIFACT_BUCKET_NAME}` S3 artifact bucket for CodePipeline

## Step-by-step commands

1. Check if GitHub OIDC provider already exists.

    ```bash
    aws iam list-open-id-connect-providers --query 'OpenIDConnectProviderList[].Arn'
    ```

2. If missing, create provider.

    ```bash
    aws iam create-open-id-connect-provider \
      --url https://token.actions.githubusercontent.com \
      --client-id-list sts.amazonaws.com \
      --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
    ```

3. Capture provider ARN.

    ```bash
    GITHUB_OIDC_PROVIDER_ARN="$(aws iam list-open-id-connect-providers \
      --query 'OpenIDConnectProviderList[?contains(Arn, `token.actions.githubusercontent.com`) == `true`].Arn | [0]' \
      --output text)"
    echo "${GITHUB_OIDC_PROVIDER_ARN}"
    ```

4. Validate OIDC trust on deployed release role (post stack deploy).

    ```bash
    aws iam get-role \
      --role-name "${PROJECT}-${APPLICATION}-github-oidc-release-role" \
      --query 'Role.AssumeRolePolicyDocument.Statement'
    ```

Expected policy conditions:

- `token.actions.githubusercontent.com:aud = sts.amazonaws.com`
- `token.actions.githubusercontent.com:sub = repo:${GITHUB_OWNER}/${GITHUB_REPO}:ref:refs/heads/${MAIN_BRANCH}`

## Required role-stack parameters

Provide these values when deploying `infra/nova/nova-iam-roles.yml` from the `nova` repository:

- `GitHubOidcProviderArn`
- `ReleaseSigningSecretArn`
- `ArtifactBucketName`
- `RepositoryOwner`
- `RepositoryName`
- `MainBranchName`

## Acceptance checks

1. `GitHubOIDCReleaseRoleArn` output exists.
2. Assume-role policy includes scoped `aud` and `sub` constraints.
3. Role has only required access to signing secret and no static keys.

## References

- IAM OIDC provider creation:
  <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html>
- OIDC secure-by-default guidance:
  <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_oidc_secure-by-default.html>
- GitHub OIDC in AWS:
  <https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws>
- IAM get-role API:
  <https://docs.aws.amazon.com/cli/latest/reference/iam/get-role.html>
