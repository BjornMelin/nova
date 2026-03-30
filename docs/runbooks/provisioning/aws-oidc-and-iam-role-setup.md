# AWS OIDC and IAM Role Setup Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-29

## Purpose

Configure the AWS IAM roles that GitHub Actions uses for Nova release and
runtime deployment automation.

## Prerequisites

1. AWS CLI configured for the target account.
2. Permission to manage IAM OIDC providers and IAM roles.
3. A CodeArtifact domain and the staging/prod repositories already exist.
4. The runtime account already has the CDK bootstrap resources and any
   environment-scoped CloudFormation execution roles required by deploy.

## Inputs

- `${AWS_REGION}` default `us-east-1`
- `${AWS_ACCOUNT_ID}`
- `${GITHUB_OWNER}`
- `${GITHUB_REPO}`
- `${MAIN_BRANCH}` default `main`
- `${SIGNING_SECRET_ARN}`
- `${RELEASE_ARTIFACT_BUCKET_ARN}`
- `${RUNTIME_CFN_EXECUTION_ROLE_ARN}`

## Required role capabilities

The release role behind `RELEASE_AWS_ROLE_ARN` must allow:

- CodeArtifact publish/read/copy for the configured staging and prod repos
- Secrets Manager read for the release signing secret
- STS assume-role via GitHub OIDC with `aud=sts.amazonaws.com`
- repository-scoped `sub` conditions for `repo:${GITHUB_OWNER}/${GITHUB_REPO}:ref:refs/heads/${MAIN_BRANCH}`

The runtime deploy role behind `RUNTIME_DEPLOY_AWS_ROLE_ARN` must allow:

- STS assume-role via GitHub OIDC with `aud=sts.amazonaws.com`
- repository-scoped `sub` conditions for `repo:${GITHUB_OWNER}/${GITHUB_REPO}:ref:refs/heads/${MAIN_BRANCH}`
- GitHub-specific `repository`, `ref`, and `job_workflow_ref` trust conditions for
  `.github/workflows/reusable-deploy-runtime.yml@refs/heads/${MAIN_BRANCH}`
- CloudFormation deploy/update/describe access for `NovaRuntimeStack`
- `ssm:GetParameter` for `/cdk-bootstrap/hnb659fds/version`
- `sts:AssumeRole` for the CDK bootstrap deploy, file-publishing, and
  image-publishing roles in the target account/region
- scoped `iam:PassRole` only for approved CloudFormation execution roles used by the runtime stack

Keep the release role and runtime deploy role separate. Package publication,
signing, and CodeArtifact promotion do not belong in the runtime deploy role.

## Authority / references

- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `docs/architecture/spec/SPEC-0027-public-api-v2.md`
- `docs/architecture/requirements.md`
- `docs/architecture/requirements-wave-2.md`
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md` through `docs/architecture/adr/ADR-0038-docs-authority-reset.md`
- `docs/architecture/spec/SPEC-0027-public-api-v2.md` through `docs/architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
- `docs/plan/GREENFIELD-WAVE-2-EXECUTION.md`
- `RELEASE_AWS_ROLE_ARN` and `RUNTIME_DEPLOY_AWS_ROLE_ARN` govern the OIDC
  setup described below

## Step-by-step commands

1. Ensure the GitHub OIDC provider exists.

    ```bash
    aws iam list-open-id-connect-providers \
      --query 'OpenIDConnectProviderList[].Arn'
    ```

2. If missing, create it.

    ```bash
    aws iam create-open-id-connect-provider \
      --url https://token.actions.githubusercontent.com \
      --client-id-list sts.amazonaws.com \
      --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
    ```

3. Create or update the release role using your account’s preferred IAM/IaC
   mechanism, then capture its ARN as `RELEASE_AWS_ROLE_ARN`.

4. Create or update the runtime deploy role using your account’s preferred
   IAM/IaC mechanism, then capture its ARN as `RUNTIME_DEPLOY_AWS_ROLE_ARN`.

5. Provision or choose the CloudFormation execution role used for runtime stack
   updates, then capture its ARN as `RUNTIME_CFN_EXECUTION_ROLE_ARN`.

6. Verify both role trust policies are scoped to the target repo and branch.

```bash
export RELEASE_AWS_ROLE_ARN="${RELEASE_AWS_ROLE_ARN:?set RELEASE_AWS_ROLE_ARN}"
export RUNTIME_DEPLOY_AWS_ROLE_ARN="${RUNTIME_DEPLOY_AWS_ROLE_ARN:?set RUNTIME_DEPLOY_AWS_ROLE_ARN}"
export RUNTIME_CFN_EXECUTION_ROLE_ARN="${RUNTIME_CFN_EXECUTION_ROLE_ARN:?set RUNTIME_CFN_EXECUTION_ROLE_ARN}"
RELEASE_ROLE_NAME="${RELEASE_AWS_ROLE_ARN##*/}"
RUNTIME_ROLE_NAME="${RUNTIME_DEPLOY_AWS_ROLE_ARN##*/}"

aws iam get-role \
  --role-name "${RELEASE_ROLE_NAME}" \
  --query 'Role.AssumeRolePolicyDocument.Statement'

aws iam get-role \
  --role-name "${RUNTIME_ROLE_NAME}" \
  --query 'Role.AssumeRolePolicyDocument.Statement'

aws iam get-role \
  --role-name "${RUNTIME_CFN_EXECUTION_ROLE_ARN##*/}" \
  --query 'Role.AssumeRolePolicyDocument.Statement'
```

## Acceptance checks

1. Both role trust policies include `aud` and repo/branch-scoped `sub`
   conditions.
2. The release role can read the signing secret and access the configured
   CodeArtifact repositories without broader wildcard permissions than
   necessary.
3. The runtime deploy role can deploy `NovaRuntimeStack`, read the immutable
   release manifest, assume only the required CDK bootstrap roles, and only
   pass approved CloudFormation execution roles.
4. The runtime execution role is trusted only by CloudFormation and owns the
   Route 53/API Gateway/WAF/Lambda/Step Functions mutations for the runtime stack.
