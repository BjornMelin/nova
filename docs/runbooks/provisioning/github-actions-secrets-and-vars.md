# GitHub Actions Secrets and Vars Setup Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-05

## Purpose

Configure repository secrets and variables required by release automation in
the target Nova repository.

## Required repository secrets

- `RELEASE_SIGNING_SECRET_ID`
- `RELEASE_AWS_ROLE_ARN`
- `AUTH0_DOMAIN` (required for `auth0-tenant-deploy.yml`)
- `AUTH0_CLIENT_ID` (required for `auth0-tenant-deploy.yml`)
- `AUTH0_CLIENT_SECRET` (required for `auth0-tenant-deploy.yml`)

## Required repository variables

- `AWS_REGION`
- `CODEARTIFACT_DOMAIN`
- `CODEARTIFACT_STAGING_REPOSITORY`
- `CODEARTIFACT_PROD_REPOSITORY`

## Prerequisites

1. GitHub CLI (`gh`) authenticated with repo admin scope.
2. Secret and role already provisioned in AWS.
3. `GITHUB_OWNER` and `GITHUB_REPO` exported for the intended repository.

## Step-by-step commands

1. Set context variables.

    ```bash
    export GITHUB_OWNER="${GITHUB_OWNER:?set to the target GitHub org or user}"
    export GITHUB_REPO="${GITHUB_REPO:?set to the target GitHub repository}"
    export GH_REPO="${GITHUB_OWNER}/${GITHUB_REPO}"
    export RELEASE_SIGNING_SECRET_ID="nova/release/signing-key"
    export RELEASE_AWS_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/nova-ci-github-oidc-release-role"
    export AUTH0_DOMAIN="your-tenant.us.auth0.com"
    export AUTH0_CLIENT_ID="auth0-machine-client-id"
    export AUTH0_CLIENT_SECRET="auth0-machine-client-secret"
    export AWS_REGION="us-east-1"
    export CODEARTIFACT_DOMAIN="cral"
    export CODEARTIFACT_STAGING_REPOSITORY="galaxypy-staging"
    export CODEARTIFACT_PROD_REPOSITORY="galaxypy-prod"
    ```

    The provisioning command pack and supporting GitHub setup commands use the
    explicit `GITHUB_OWNER` / `GITHUB_REPO` target. They do not infer the
    repository from the local checkout.

2. Set repository secrets.

    ```bash
    gh secret set RELEASE_SIGNING_SECRET_ID --repo "${GH_REPO}" --body "${RELEASE_SIGNING_SECRET_ID}"
    gh secret set RELEASE_AWS_ROLE_ARN --repo "${GH_REPO}" --body "${RELEASE_AWS_ROLE_ARN}"
    gh secret set AUTH0_DOMAIN --repo "${GH_REPO}" --body "${AUTH0_DOMAIN}"
    gh secret set AUTH0_CLIENT_ID --repo "${GH_REPO}" --body "${AUTH0_CLIENT_ID}"
    gh secret set AUTH0_CLIENT_SECRET --repo "${GH_REPO}" --body "${AUTH0_CLIENT_SECRET}"
    ```

3. Set repository variables.

    ```bash
    gh variable set AWS_REGION --repo "${GH_REPO}" --body "${AWS_REGION}"
    gh variable set CODEARTIFACT_DOMAIN --repo "${GH_REPO}" --body "${CODEARTIFACT_DOMAIN}"
    gh variable set CODEARTIFACT_STAGING_REPOSITORY --repo "${GH_REPO}" --body "${CODEARTIFACT_STAGING_REPOSITORY}"
    gh variable set CODEARTIFACT_PROD_REPOSITORY --repo "${GH_REPO}" --body "${CODEARTIFACT_PROD_REPOSITORY}"
    ```

4. Verify current values exist.

    ```bash
    gh secret list --repo "${GH_REPO}"
    gh variable list --repo "${GH_REPO}"
    ```

## Workflow contracts

Configured values are consumed by:

- `release-apply.yml`
  - `SIGNING_SECRET_ID: ${{ secrets.RELEASE_SIGNING_SECRET_ID }}`
  - `RELEASE_AWS_ROLE_ARN: ${{ secrets.RELEASE_AWS_ROLE_ARN }}`
  - `AWS_REGION: ${{ vars.AWS_REGION || 'us-east-1' }}`
- Package/deploy/promote workflows
  - `RELEASE_AWS_ROLE_ARN: ${{ secrets.RELEASE_AWS_ROLE_ARN }}`
  - `CODEARTIFACT_DOMAIN: ${{ vars.CODEARTIFACT_DOMAIN }}`
  - `CODEARTIFACT_STAGING_REPOSITORY: ${{ vars.CODEARTIFACT_STAGING_REPOSITORY }}`
  - `CODEARTIFACT_PROD_REPOSITORY: ${{ vars.CODEARTIFACT_PROD_REPOSITORY }}`
- Auth0 tenant deploy workflows
  - `auth0-tenant-deploy.yml`
  - `reusable-auth0-tenant-deploy.yml`
- Post-deploy validation workflows
  - `post-deploy-validate.yml` (manual wrapper)
  - `reusable-post-deploy-validate.yml` (`workflow_call` API)

`Publish Packages` is the manual staging publish workflow for Python,
TypeScript/npm, and R artifacts. `Promote Prod` is the manual prod promotion
workflow for the staged, gate-validated artifacts.

## Branch/signature policy checks

1. Ensure branch target for release is `main`.
2. Ensure signed release commit verification workflow is enabled:
   - `.github/workflows/verify-signature.yml`
3. Ensure branch protection/ruleset requires checks to pass.

## References

- GitHub encrypted secrets:
  <https://docs.github.com/en/actions/security-for-github-actions/security-guides/encrypted-secrets>
- GitHub Actions variables:
  <https://docs.github.com/en/actions/learn-github-actions/variables>
- GitHub CLI secret command:
  <https://cli.github.com/manual/gh_secret_set>
- GitHub CLI variable command:
  <https://cli.github.com/manual/gh_variable_set>
- Downstream integration guide:
  `../../clients/post-deploy-validation-integration-guide.md`
