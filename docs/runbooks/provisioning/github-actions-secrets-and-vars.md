# GitHub Actions Secrets and Vars Setup Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-29

## Purpose

Configure the GitHub repository secrets and variables required by the surviving
Nova release workflows.

## Authority / references

- `docs/architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md` (canonical route-surface authority)
- `docs/architecture/spec/superseded/SPEC-0000-http-api-contract.md` (historical API baseline reference for hard-cut context)
- `docs/architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md` (active route-surface guardrails)
- `docs/architecture/spec/SPEC-0027-public-api-v2.md`
- `docs/architecture/requirements.md`
- `docs/plan/GREENFIELD-WAVE-2-EXECUTION.md`
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md` through `docs/architecture/adr/ADR-0038-docs-authority-reset.md` (active deployment and docs authority block)
- `docs/architecture/spec/SPEC-0027-public-api-v2.md` through `docs/architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md` (active API and docs authority block)

## Required repository secrets

- `RELEASE_SIGNING_SECRET_ID`
- `RELEASE_AWS_ROLE_ARN`
- `RUNTIME_DEPLOY_AWS_ROLE_ARN`
- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`

## Required repository variables

- `AWS_REGION`
- `CODEARTIFACT_DOMAIN`
- `CODEARTIFACT_STAGING_REPOSITORY`
- `CODEARTIFACT_PROD_REPOSITORY`
- `RELEASE_ARTIFACT_BUCKET`
- `RUNTIME_ENVIRONMENT`
- `RUNTIME_API_DOMAIN_NAME`
- `RUNTIME_CERTIFICATE_ARN`
- `RUNTIME_HOSTED_ZONE_ID`
- `RUNTIME_HOSTED_ZONE_NAME`
- `RUNTIME_CFN_EXECUTION_ROLE_ARN`
- `RUNTIME_JWT_ISSUER`
- `RUNTIME_JWT_AUDIENCE`
- `RUNTIME_JWT_JWKS_URL`
- `RUNTIME_ALLOWED_ORIGINS`

## Step-by-step commands

```bash
export GITHUB_OWNER="${GITHUB_OWNER:?set the target GitHub org or user}"
export GITHUB_REPO="${GITHUB_REPO:?set the target GitHub repository}"
export GH_REPO="${GITHUB_OWNER}/${GITHUB_REPO}"
export RELEASE_SIGNING_SECRET_ID="${RELEASE_SIGNING_SECRET_ID:?set RELEASE_SIGNING_SECRET_ID}"
export RELEASE_AWS_ROLE_ARN="${RELEASE_AWS_ROLE_ARN:?set RELEASE_AWS_ROLE_ARN}"
export RUNTIME_DEPLOY_AWS_ROLE_ARN="${RUNTIME_DEPLOY_AWS_ROLE_ARN:?set RUNTIME_DEPLOY_AWS_ROLE_ARN}"
export AUTH0_DOMAIN="${AUTH0_DOMAIN:?set AUTH0_DOMAIN}"
export AUTH0_CLIENT_ID="${AUTH0_CLIENT_ID:?set AUTH0_CLIENT_ID}"
export AUTH0_CLIENT_SECRET="${AUTH0_CLIENT_SECRET:?set AUTH0_CLIENT_SECRET}"
export AWS_REGION="${AWS_REGION:?set AWS_REGION}"
export CODEARTIFACT_DOMAIN="${CODEARTIFACT_DOMAIN:?set CODEARTIFACT_DOMAIN}"
export CODEARTIFACT_STAGING_REPOSITORY="${CODEARTIFACT_STAGING_REPOSITORY:?set CODEARTIFACT_STAGING_REPOSITORY}"
export CODEARTIFACT_PROD_REPOSITORY="${CODEARTIFACT_PROD_REPOSITORY:?set CODEARTIFACT_PROD_REPOSITORY}"
export RELEASE_ARTIFACT_BUCKET="${RELEASE_ARTIFACT_BUCKET:?set RELEASE_ARTIFACT_BUCKET}"
export RUNTIME_ENVIRONMENT="${RUNTIME_ENVIRONMENT:?set RUNTIME_ENVIRONMENT}"
export RUNTIME_API_DOMAIN_NAME="${RUNTIME_API_DOMAIN_NAME:?set RUNTIME_API_DOMAIN_NAME}"
export RUNTIME_CERTIFICATE_ARN="${RUNTIME_CERTIFICATE_ARN:?set RUNTIME_CERTIFICATE_ARN}"
export RUNTIME_HOSTED_ZONE_ID="${RUNTIME_HOSTED_ZONE_ID:?set RUNTIME_HOSTED_ZONE_ID}"
export RUNTIME_HOSTED_ZONE_NAME="${RUNTIME_HOSTED_ZONE_NAME:?set RUNTIME_HOSTED_ZONE_NAME}"
export RUNTIME_CFN_EXECUTION_ROLE_ARN="${RUNTIME_CFN_EXECUTION_ROLE_ARN:?set RUNTIME_CFN_EXECUTION_ROLE_ARN}"
export RUNTIME_JWT_ISSUER="${RUNTIME_JWT_ISSUER:?set RUNTIME_JWT_ISSUER}"
export RUNTIME_JWT_AUDIENCE="${RUNTIME_JWT_AUDIENCE:?set RUNTIME_JWT_AUDIENCE}"
export RUNTIME_JWT_JWKS_URL="${RUNTIME_JWT_JWKS_URL:?set RUNTIME_JWT_JWKS_URL}"
export RUNTIME_ALLOWED_ORIGINS="${RUNTIME_ALLOWED_ORIGINS:-}"

gh secret set RELEASE_SIGNING_SECRET_ID --repo "${GH_REPO}" --body "${RELEASE_SIGNING_SECRET_ID}"
gh secret set RELEASE_AWS_ROLE_ARN --repo "${GH_REPO}" --body "${RELEASE_AWS_ROLE_ARN}"
gh secret set RUNTIME_DEPLOY_AWS_ROLE_ARN --repo "${GH_REPO}" --body "${RUNTIME_DEPLOY_AWS_ROLE_ARN}"
gh secret set AUTH0_DOMAIN --repo "${GH_REPO}" --body "${AUTH0_DOMAIN}"
gh secret set AUTH0_CLIENT_ID --repo "${GH_REPO}" --body "${AUTH0_CLIENT_ID}"
gh secret set AUTH0_CLIENT_SECRET --repo "${GH_REPO}" --body "${AUTH0_CLIENT_SECRET}"

gh variable set AWS_REGION --repo "${GH_REPO}" --body "${AWS_REGION}"
gh variable set CODEARTIFACT_DOMAIN --repo "${GH_REPO}" --body "${CODEARTIFACT_DOMAIN}"
gh variable set CODEARTIFACT_STAGING_REPOSITORY --repo "${GH_REPO}" --body "${CODEARTIFACT_STAGING_REPOSITORY}"
gh variable set CODEARTIFACT_PROD_REPOSITORY --repo "${GH_REPO}" --body "${CODEARTIFACT_PROD_REPOSITORY}"
gh variable set RELEASE_ARTIFACT_BUCKET --repo "${GH_REPO}" --body "${RELEASE_ARTIFACT_BUCKET}"
gh variable set RUNTIME_ENVIRONMENT --repo "${GH_REPO}" --body "${RUNTIME_ENVIRONMENT}"
gh variable set RUNTIME_API_DOMAIN_NAME --repo "${GH_REPO}" --body "${RUNTIME_API_DOMAIN_NAME}"
gh variable set RUNTIME_CERTIFICATE_ARN --repo "${GH_REPO}" --body "${RUNTIME_CERTIFICATE_ARN}"
gh variable set RUNTIME_HOSTED_ZONE_ID --repo "${GH_REPO}" --body "${RUNTIME_HOSTED_ZONE_ID}"
gh variable set RUNTIME_HOSTED_ZONE_NAME --repo "${GH_REPO}" --body "${RUNTIME_HOSTED_ZONE_NAME}"
gh variable set RUNTIME_CFN_EXECUTION_ROLE_ARN --repo "${GH_REPO}" --body "${RUNTIME_CFN_EXECUTION_ROLE_ARN}"
gh variable set RUNTIME_JWT_ISSUER --repo "${GH_REPO}" --body "${RUNTIME_JWT_ISSUER}"
gh variable set RUNTIME_JWT_AUDIENCE --repo "${GH_REPO}" --body "${RUNTIME_JWT_AUDIENCE}"
gh variable set RUNTIME_JWT_JWKS_URL --repo "${GH_REPO}" --body "${RUNTIME_JWT_JWKS_URL}"
gh variable set RUNTIME_ALLOWED_ORIGINS --repo "${GH_REPO}" --body "${RUNTIME_ALLOWED_ORIGINS}"
```

## Consumed by

- `release-apply.yml`
- `deploy-runtime.yml`
- `reusable-deploy-runtime.yml`
- `publish-packages.yml`
- `promote-prod.yml`
- `auth0-tenant-deploy.yml`
- `reusable-auth0-tenant-deploy.yml`
