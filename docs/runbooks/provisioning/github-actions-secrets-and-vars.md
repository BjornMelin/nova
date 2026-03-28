# GitHub Actions Secrets and Vars Setup Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-28

## Purpose

Configure the GitHub repository secrets and variables required by the surviving
Nova release workflows.

## Required repository secrets

- `RELEASE_SIGNING_SECRET_ID`
- `RELEASE_AWS_ROLE_ARN`
- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`

## Required repository variables

- `AWS_REGION`
- `CODEARTIFACT_DOMAIN`
- `CODEARTIFACT_STAGING_REPOSITORY`
- `CODEARTIFACT_PROD_REPOSITORY`

## Step-by-step commands

```bash
export GITHUB_OWNER="${GITHUB_OWNER:?set the target GitHub org or user}"
export GITHUB_REPO="${GITHUB_REPO:?set the target GitHub repository}"
export GH_REPO="${GITHUB_OWNER}/${GITHUB_REPO}"

gh secret set RELEASE_SIGNING_SECRET_ID --repo "${GH_REPO}" --body "${RELEASE_SIGNING_SECRET_ID}"
gh secret set RELEASE_AWS_ROLE_ARN --repo "${GH_REPO}" --body "${RELEASE_AWS_ROLE_ARN}"
gh secret set AUTH0_DOMAIN --repo "${GH_REPO}" --body "${AUTH0_DOMAIN}"
gh secret set AUTH0_CLIENT_ID --repo "${GH_REPO}" --body "${AUTH0_CLIENT_ID}"
gh secret set AUTH0_CLIENT_SECRET --repo "${GH_REPO}" --body "${AUTH0_CLIENT_SECRET}"

gh variable set AWS_REGION --repo "${GH_REPO}" --body "${AWS_REGION}"
gh variable set CODEARTIFACT_DOMAIN --repo "${GH_REPO}" --body "${CODEARTIFACT_DOMAIN}"
gh variable set CODEARTIFACT_STAGING_REPOSITORY --repo "${GH_REPO}" --body "${CODEARTIFACT_STAGING_REPOSITORY}"
gh variable set CODEARTIFACT_PROD_REPOSITORY --repo "${GH_REPO}" --body "${CODEARTIFACT_PROD_REPOSITORY}"
```

## Consumed by

- `release-apply.yml`
- `publish-packages.yml`
- `promote-prod.yml`
- `auth0-tenant-deploy.yml`
- `reusable-auth0-tenant-deploy.yml`
- `post-deploy-validate.yml`
- `reusable-post-deploy-validate.yml`
