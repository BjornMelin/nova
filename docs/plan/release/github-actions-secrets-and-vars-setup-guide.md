# GitHub Actions Secrets and Vars Setup Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

Configure repository secrets and variables required by release automation in
`3M-Cloud/nova`.

## Required repository secrets

- `RELEASE_SIGNING_SECRET_ID`
- `RELEASE_AWS_ROLE_ARN`

## Required repository variables

- `AWS_REGION`

## Prerequisites

1. GitHub CLI (`gh`) authenticated with repo admin scope.
2. Secret and role already provisioned in AWS.

## Step-by-step commands

1. Set context variables.

    ```bash
    export GH_REPO="3M-Cloud/nova"
    export RELEASE_SIGNING_SECRET_ID="nova/release/signing-key"
    export RELEASE_AWS_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/nova-ci-github-oidc-release-role"
    export AWS_REGION="us-east-1"
    ```

2. Set repository secrets.

    ```bash
    gh secret set RELEASE_SIGNING_SECRET_ID --repo "${GH_REPO}" --body "${RELEASE_SIGNING_SECRET_ID}"
    gh secret set RELEASE_AWS_ROLE_ARN --repo "${GH_REPO}" --body "${RELEASE_AWS_ROLE_ARN}"
    ```

3. Set repository variable.

    ```bash
    gh variable set AWS_REGION --repo "${GH_REPO}" --body "${AWS_REGION}"
    ```

4. Verify current values exist.

    ```bash
    gh secret list --repo "${GH_REPO}"
    gh variable list --repo "${GH_REPO}"
    ```

## Workflow contracts

Configured values are consumed by:

- `publish-packages.yml`
  - `SIGNING_SECRET_ID: ${{ secrets.RELEASE_SIGNING_SECRET_ID }}`
  - `RELEASE_AWS_ROLE_ARN: ${{ secrets.RELEASE_AWS_ROLE_ARN }}`
  - `AWS_REGION: ${{ vars.AWS_REGION || 'us-east-1' }}`

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
