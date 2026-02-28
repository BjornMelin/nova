# Day-0 Operator Checklist

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

Execute first-time Nova CI/CD provisioning and release promotion in one ordered
operator checklist.

## Prerequisites

1. AWS CLI v2 installed and authenticated.
2. GitHub CLI installed and authenticated.
3. Access to both repositories:
   - `3M-Cloud/nova`
   - `3M-Cloud/container-craft`
4. Release stack configuration values prepared.

## Inputs

- `${AWS_REGION}`
- `${AWS_ACCOUNT_ID}`
- `${PROJECT}` default `container-craft`
- `${APPLICATION}` default `ci`
- `${GITHUB_OWNER}` default `3M-Cloud`
- `${GITHUB_REPO}` default `nova`
- `${SIGNER_NAME}`
- `${SIGNER_EMAIL}`
- `${SECRET_NAME}` default `nova/release/signing-key`

## Single command-pack script (recommended)

Use the operator script for end-to-end execution:

- script path: `scripts/release/day-0-operator-command-pack.sh`

Copy/paste run example:

```bash
cd ~/repos/work/infra-stack/nova

export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=123456789012
export SIGNER_NAME="Nova Release Bot"
export SIGNER_EMAIL="nova-release@example.com"
export GITHUB_OIDC_PROVIDER_ARN="arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
export NOVA_ARTIFACT_BUCKET_NAME="container-craft-ci-artifacts"
export NOVA_DEV_SERVICE_BASE_URL="https://dev.example.com"
export NOVA_PROD_SERVICE_BASE_URL="https://prod.example.com"

./scripts/release/day-0-operator-command-pack.sh
```

Optional behavior:

- set `TRIGGER_WORKFLOWS=false` to skip dispatching release workflows.
- set `TRIGGER_RELEASE_APPLY_DIRECT=true` only when explicit manual Apply
  dispatch is required (default keeps Apply chained from Plan workflow_run).

## Step-by-step commands

1. Generate and store release signing secret.

    ```bash
    ssh-keygen -t ed25519 -C "${SIGNER_EMAIL}" -N "" -f /tmp/nova-release-signing

    cat >/tmp/nova-release-signing-secret.json <<JSON
    {
      "private_key": $(jq -Rs . </tmp/nova-release-signing),
      "public_key": $(jq -Rs . </tmp/nova-release-signing.pub),
      "signer_name": "${SIGNER_NAME}",
      "signer_email": "${SIGNER_EMAIL}"
    }
    JSON

    aws secretsmanager create-secret \
      --region "${AWS_REGION}" \
      --name "${SECRET_NAME}" \
      --description "Nova release SSH signing key" \
      --secret-string file:///tmp/nova-release-signing-secret.json || \
    aws secretsmanager put-secret-value \
      --region "${AWS_REGION}" \
      --secret-id "${SECRET_NAME}" \
      --secret-string file:///tmp/nova-release-signing-secret.json

    # Cleanup local secret material immediately after upload.
    rm -f /tmp/nova-release-signing \
      /tmp/nova-release-signing.pub \
      /tmp/nova-release-signing-secret.json
    ```

2. Deploy Nova CI/CD stacks from `container-craft` using `deploy-nova-cicd`.

    ```bash
    # Run via your standard container-craft GitHub workflow with:
    # run=deploy-nova-cicd
    # stack_action=update
    ```

3. Capture stack outputs.

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

4. Set GitHub secrets and variable in `3M-Cloud/nova`.

    ```bash
    export GH_REPO="${GITHUB_OWNER}/${GITHUB_REPO}"

    gh secret set RELEASE_SIGNING_SECRET_ID --repo "${GH_REPO}" --body "${SECRET_NAME}"
    gh secret set RELEASE_AWS_ROLE_ARN --repo "${GH_REPO}" --body "${RELEASE_AWS_ROLE_ARN}"
    gh variable set AWS_REGION --repo "${GH_REPO}" --body "${AWS_REGION}"
    ```

5. Activate CodeConnections if needed.

    ```bash
    aws codeconnections get-connection \
      --region "${AWS_REGION}" \
      --connection-arn "${CONNECTION_ARN}" \
      --query 'Connection.ConnectionStatus' \
      --output text
    ```

    If status is `PENDING`, authorize the connection in AWS Console.

6. Run release workflows.

    ```bash
    gh workflow run "Nova Release Plan" --repo "${GH_REPO}" --ref main
    gh workflow run "Nova Release Apply" --repo "${GH_REPO}" --ref main
    ```

7. Validate pipeline stages and approve production promotion.

    ```bash
    aws codepipeline list-pipeline-executions \
      --region "${AWS_REGION}" \
      --pipeline-name "${CODEPIPELINE_NAME}" \
      --max-results 5

    aws codepipeline get-pipeline-state \
      --region "${AWS_REGION}" \
      --name "${CODEPIPELINE_NAME}"
    ```

8. Record evidence in runbooks and plans.

   - `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
   - `docs/plan/PLAN.md`
   - `FINAL-PLAN.md`

## Acceptance checks

1. Release commit signature is verified in GitHub.
2. CodeConnections status is `AVAILABLE`.
3. Pipeline completes Dev -> ManualApproval -> Prod in order.
4. `IMAGE_DIGEST` continuity is preserved from Dev to Prod.

## References

- [documentation-index.md](documentation-index.md)
- [deploy-nova-cicd-end-to-end-guide.md](deploy-nova-cicd-end-to-end-guide.md)
- [release-promotion-dev-to-prod-guide.md](release-promotion-dev-to-prod-guide.md)
- [troubleshooting-and-break-glass-guide.md](troubleshooting-and-break-glass-guide.md)
- GitHub OIDC docs:
  <https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws>
- CodePipeline approvals docs:
  <https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-action-add.html>
