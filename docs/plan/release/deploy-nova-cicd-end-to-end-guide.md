# Deploy Nova CI/CD End-to-End Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

Provide a complete deploy sequence for Nova CI/CD resources and first release
execution.

## Prerequisites

1. `container-craft` repo access and action execution permissions.
2. AWS credentials configured for stack deployment account.
3. Release signing secret created in Secrets Manager.
4. GitHub OIDC provider and trust role setup completed.
5. `nova` repository admin rights for secrets/variables configuration.

## Deployment model

Primary path:

1. Deploy infrastructure via `container-craft` with `run=deploy-nova-cicd`.
2. Configure `nova` repository secrets/vars.
3. Activate CodeConnections.
4. Run release workflows and validate AWS promotion.

Fallback path:

- use direct AWS CLI/CloudFormation commands documented in
  [troubleshooting-and-break-glass-guide.md](troubleshooting-and-break-glass-guide.md)

## Inputs checklist

- `${AWS_REGION}`
- `${PROJECT}` default `container-craft`
- `${APPLICATION}` default `ci`
- `${CONFIG_FILE}` service YAML used by container-craft
- `${CONFIG_DIR}` directory containing `${CONFIG_FILE}`
- `${GITHUB_OWNER}` default `BjornMelin`
- `${GITHUB_REPO}` default `nova`

## Step 1: prepare container-craft config values

Set required keys in service config:

- `github_oidc_provider_arn`
- `release_signing_secret_arn`
- `nova_artifact_bucket_name`
- `nova_ecr_repository_uri` or `nova_ecr_repository_name`
- `nova_dev_service_base_url`
- `nova_prod_service_base_url`
- optional: `nova_existing_connection_arn`

Reference details:
[config-values-reference-guide.md](config-values-reference-guide.md)

## Step 2: deploy CI/CD stacks via action

Use a GitHub workflow in `container-craft` that calls the composite action with:

- `run: deploy-nova-cicd`
- `stack_action: update`
- `environ: dev` (or your deployment environment)

Minimal invocation:

```yaml
- name: Deploy Nova CI/CD stacks
  uses: 3M-Cloud/container-craft@main
  with:
    config_dir: ${CONFIG_DIR}
    config_file: ${CONFIG_FILE}
    environ: dev
    aws_region: ${AWS_REGION}
    run: deploy-nova-cicd
    stack_action: update
```

## Step 3: capture stack outputs

```bash
aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-iam-roles" \
  --query 'Stacks[0].Outputs'

aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-ci-cd" \
  --query 'Stacks[0].Outputs'
```

Record:

- `GitHubOIDCReleaseRoleArn`
- `PipelineName`
- `ConnectionArn`

## Step 4: configure GitHub repo secrets and vars

Run setup from:
[github-actions-secrets-and-vars-setup-guide.md](github-actions-secrets-and-vars-setup-guide.md)

## Step 5: activate CodeConnections

Run activation checks from:
[codeconnections-activation-and-validation-guide.md](codeconnections-activation-and-validation-guide.md)

## Step 6: run release plan and apply

```bash
gh workflow run "Nova Release Plan" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main
gh workflow run "Nova Release Apply" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main
```

## Step 7: validate pipeline promotion path

Expected stage order:

1. `Source`
2. `Build`
3. `DeployDev`
4. `ValidateDev`
5. `ManualApproval`
6. `DeployProd`
7. `ValidateProd`

Validate with:

```bash
aws codepipeline get-pipeline-state \
  --region "${AWS_REGION}" \
  --name "${CODEPIPELINE_NAME}"
```

## References

- CodePipeline get-pipeline-state API:
  <https://docs.aws.amazon.com/cli/latest/reference/codepipeline/get-pipeline-state.html>
- GitHub workflow dispatch with CLI:
  <https://cli.github.com/manual/gh_workflow_run>
