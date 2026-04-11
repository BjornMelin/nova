# GitHub Actions Secrets and Vars Setup Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-04-10

## Purpose

Configure the minimal GitHub Environment secrets required by the surviving Nova
GitHub workflows.

GitHub is no longer a supported publish, deploy, or promotion executor. It
retains PR CI, manual release planning preview, post-deploy validation, and
Auth0 workflow surfaces. The AWS-native release control plane is provisioned
through `infra/nova_cdk` and reads its runtime deploy configuration from SSM
Parameter Store plus AWS Secrets Manager.

## Authority / references

- `docs/contracts/deploy-output-authority-v2.schema.json`
- `docs/contracts/workflow-post-deploy-validate.schema.json`
- `docs/runbooks/release/release-runbook.md`
- `infra/nova_cdk/README.md`

## Required GitHub Environment secrets

Create one GitHub Environment per Auth0 tenant surface:

- `auth0-dev`
- `auth0-pr`
- `auth0-qa`

Each environment stores the credentials for the matching
`nova-tenant-ops-<env>` M2M application:

- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`

## Step-by-step commands

```bash
export GITHUB_OWNER="${GITHUB_OWNER:?set the target GitHub org or user}"
export GITHUB_REPO="${GITHUB_REPO:?set the target GitHub repository}"
export GH_REPO="${GITHUB_OWNER}/${GITHUB_REPO}"
for ENVIRONMENT in auth0-dev auth0-pr auth0-qa; do
  read -r AUTH0_DOMAIN
  read -r AUTH0_CLIENT_ID
  read -r -s AUTH0_CLIENT_SECRET
  printf '\n'
  printf '%s' "${AUTH0_DOMAIN}" | gh secret set AUTH0_DOMAIN --repo "${GH_REPO}" --env "${ENVIRONMENT}"
  printf '%s' "${AUTH0_CLIENT_ID}" | gh secret set AUTH0_CLIENT_ID --repo "${GH_REPO}" --env "${ENVIRONMENT}"
  printf '%s' "${AUTH0_CLIENT_SECRET}" | gh secret set AUTH0_CLIENT_SECRET --repo "${GH_REPO}" --env "${ENVIRONMENT}"
  unset AUTH0_DOMAIN AUTH0_CLIENT_ID AUTH0_CLIENT_SECRET
done
```

## Consumed by

- `auth0-tenant-deploy.yml`
- `reusable-auth0-tenant-deploy.yml`

## Rule

Do not add repository variables for runtime deploy coordinates, CodeArtifact
repositories, or release executor settings that now belong to the AWS-native
release control plane.

Do not duplicate Auth0 tenant credentials as repo-wide secrets. The reusable
workflow selects the GitHub Environment named `auth0-${environment}` and reads
its secrets directly.
