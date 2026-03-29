# AWS OIDC and IAM Role Setup Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-28

## Purpose

Configure the AWS IAM role that GitHub Actions uses for Nova release
automation.

## Prerequisites

1. AWS CLI configured for the target account.
2. Permission to manage IAM OIDC providers and IAM roles.
3. A CodeArtifact domain and the staging/prod repositories already exist.

## Inputs

- `${AWS_REGION}` default `us-east-1`
- `${AWS_ACCOUNT_ID}`
- `${GITHUB_OWNER}`
- `${GITHUB_REPO}`
- `${MAIN_BRANCH}` default `main`
- `${SIGNING_SECRET_ARN}`

## Required role capabilities

The release role behind `RELEASE_AWS_ROLE_ARN` must allow:

- CodeArtifact publish/read/copy for the configured staging and prod repos
- Secrets Manager read for the release signing secret
- STS assume-role via GitHub OIDC with `aud=sts.amazonaws.com`
- repository-scoped `sub` conditions for `repo:${GITHUB_OWNER}/${GITHUB_REPO}:ref:refs/heads/${MAIN_BRANCH}`

## Authority / references

- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `docs/architecture/spec/SPEC-0000-http-api-contract.md`
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `docs/architecture/requirements-wave-2.md`
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md` through `docs/architecture/adr/ADR-0038-docs-authority-reset.md`
- `docs/architecture/spec/SPEC-0027-public-api-v2.md` through `docs/architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`
- `RELEASE_AWS_ROLE_ARN` and the release role trust policy govern the OIDC setup described below

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

4. Verify the role trust policy is scoped to the target repo and branch.

```bash
export RELEASE_AWS_ROLE_ARN="${RELEASE_AWS_ROLE_ARN:?set RELEASE_AWS_ROLE_ARN}"
ROLE_NAME="${RELEASE_AWS_ROLE_ARN##*/}"

aws iam get-role \
  --role-name "${ROLE_NAME}" \
  --query 'Role.AssumeRolePolicyDocument.Statement'
```

## Acceptance checks

1. The role trust policy includes both `aud` and repo/branch-scoped `sub`
   conditions.
2. The role can read the signing secret and access the configured CodeArtifact
   repositories without broader wildcard permissions than necessary.
