# AWS OIDC and IAM Role Setup Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-05

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
- `${FOUNDATION_STACK_NAME}` default: `${PROJECT}-${APPLICATION}-nova-foundation`
- `${CODEARTIFACT_STAGING_REPOSITORY}` example: `galaxypy-staging`
- `${CODEARTIFACT_PROD_REPOSITORY}` example: `galaxypy-prod`

Repository directionality contract:

- Staging repo is the promotion source.
- Prod repo is the promotion destination.
- Source and destination repositories must not be identical.

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

4. Deploy IAM role stack from `infra/nova/nova-iam-roles.yml`.

    ```bash
    FOUNDATION_STACK_NAME="${FOUNDATION_STACK_NAME:-${PROJECT}-${APPLICATION}-nova-foundation}"

    aws cloudformation deploy \
      --region "${AWS_REGION}" \
      --stack-name "${PROJECT}-${APPLICATION}-nova-iam-roles" \
      --template-file infra/nova/nova-iam-roles.yml \
      --capabilities CAPABILITY_NAMED_IAM \
      --parameter-overrides \
        Project="${PROJECT}" \
        Application="${APPLICATION}" \
        FoundationStackName="${FOUNDATION_STACK_NAME}" \
        RepositoryOwner="${GITHUB_OWNER}" \
        RepositoryName="${GITHUB_REPO}" \
        MainBranchName="${MAIN_BRANCH}" \
        GitHubOidcProviderArn="${GITHUB_OIDC_PROVIDER_ARN}" \
        ReleaseSigningSecretArn="${SIGNING_SECRET_ARN}" \
        CodeArtifactPromotionSourceRepositoryName="${CODEARTIFACT_STAGING_REPOSITORY}" \
        CodeArtifactPromotionDestinationRepositoryName="${CODEARTIFACT_PROD_REPOSITORY}"
    ```

5. Validate OIDC trust on deployed release role (post stack deploy).

    ```bash
    aws iam get-role \
      --role-name "${PROJECT}-${APPLICATION}-github-oidc-release-role" \
      --query 'Role.AssumeRolePolicyDocument.Statement'
    ```

Expected policy conditions:

- `token.actions.githubusercontent.com:aud = sts.amazonaws.com`
- `token.actions.githubusercontent.com:sub = repo:${GITHUB_OWNER}/${GITHUB_REPO}:ref:refs/heads/${MAIN_BRANCH}`

## Required role-stack parameters

Provide these values when deploying `infra/nova/nova-iam-roles.yml`:

- `GitHubOidcProviderArn`
- `ReleaseSigningSecretArn`
- `FoundationStackName` (or explicit artifact/CodeArtifact/ECR overrides)
- `RepositoryOwner`
- `RepositoryName`
- `MainBranchName`
- `CodeArtifactPromotionSourceRepositoryName`
- `CodeArtifactPromotionDestinationRepositoryName`

## Acceptance checks

1. `GitHubOIDCReleaseRoleArn` output exists:

   ```bash
   aws cloudformation describe-stacks \
     --region "${AWS_REGION}" \
     --stack-name "${PROJECT}-${APPLICATION}-nova-iam-roles" \
     --query 'Stacks[0].Outputs[?OutputKey==`GitHubOIDCReleaseRoleArn`].OutputValue | [0]' \
     --output text
   ```
2. Assume-role policy includes scoped `aud` and `sub` constraints.
3. Role has only required access to signing secret and no static keys.
4. Promotion permissions are directional:
   - `codeartifact:ReadFromRepository` scoped to staging source repository.
   - `codeartifact:CopyPackageVersions` scoped to prod destination repository
     plus required package ARNs.

## References

- IAM OIDC provider creation:
  <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html>
- OIDC secure-by-default guidance:
  <https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_oidc_secure-by-default.html>
- GitHub OIDC in AWS:
  <https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws>
- IAM get-role API:
  <https://docs.aws.amazon.com/cli/latest/reference/iam/get-role.html>
