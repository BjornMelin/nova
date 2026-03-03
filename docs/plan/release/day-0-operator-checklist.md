# Day-0 Operator Checklist (Minimal Path)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-02

## Purpose

Run first-time Nova CI/CD provisioning and release promotion using the shortest
safe operator path.

## Prerequisites

1. AWS CLI v2 authenticated.
2. GitHub CLI authenticated.
3. Repository admin access to `${GITHUB_OWNER}/${GITHUB_REPO}` (default: `3M-Cloud/nova`).
4. Required environment values prepared.

## Inputs

- `${AWS_REGION}` (required, e.g., `us-east-1`)
- `${AWS_ACCOUNT_ID}` (required, e.g., `123456789012`)
- `${PROJECT}` (default `nova`)
- `${APPLICATION}` (default `ci`)
- `${GITHUB_OWNER}` (default `3M-Cloud`)
- `${GITHUB_REPO}` (default `nova`)
- `${CONNECTION_ARN}` (required, e.g.,
  `arn:aws:codestar-connections:us-east-1:...:connection/xxxxxxxx`)
- `${NAMESPACE}` (default `nova`)
- `${API_DEPLOYMENT_NAME}` (required, e.g., `${APPLICATION}-api`)
- `${APP_LABEL}` (required, e.g., `${APPLICATION}-api`)
- `${AWS_ROLE_TO_ASSUME}` (required if using GitHub OIDC role chaining)
- `${GITHUB_WEBHOOK_SECRET_NAME}` (optional)

## Step-by-step commands

### Step 1: Export required values

```bash
export AWS_REGION="${AWS_REGION:?Set AWS_REGION}"
export AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
export PROJECT="${PROJECT:-nova}"
export APPLICATION="${APPLICATION:-ci}"
export GITHUB_OWNER="${GITHUB_OWNER:-3M-Cloud}"
export GITHUB_REPO="${GITHUB_REPO:-nova}"
export CONNECTION_ARN="${CONNECTION_ARN:?Set CONNECTION_ARN}"
export NAMESPACE="${NAMESPACE:?Set NAMESPACE}"
export API_DEPLOYMENT_NAME="${API_DEPLOYMENT_NAME:?Set API_DEPLOYMENT_NAME}"
export APP_LABEL="${APP_LABEL:?Set APP_LABEL}"
export BATCHB_VALIDATION_ROLE_NAME="${PROJECT}-${APPLICATION}-batch-b-validation-operator-role"
```

### Step 2: Run command pack

```bash
./scripts/release/day-0-operator-command-pack.sh
```

### Step 3: Validate stack outputs

```bash
aws cloudformation describe-stacks --region "${AWS_REGION}" --stack-name "${PROJECT}-${APPLICATION}-nova-iam-roles" --query 'Stacks[0].Outputs'
aws cloudformation describe-stacks --region "${AWS_REGION}" --stack-name "${PROJECT}-${APPLICATION}-nova-ci-cd" --query 'Stacks[0].Outputs'
```

### Step 4: Verify GitHub wiring is complete

```bash
required_secrets=(AWS_ROLE_TO_ASSUME AWS_REGION)
required_vars=(PROJECT APPLICATION)

existing_secrets="$(gh secret list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --json name -q '.[].name')"
existing_vars="$(gh variable list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --json name -q '.[].name')"

for key in "${required_secrets[@]}"; do
  grep -qx "${key}" <<< "${existing_secrets}" || { echo "Missing secret: ${key}"; exit 1; }
done
for key in "${required_vars[@]}"; do
  grep -qx "${key}" <<< "${existing_vars}" || { echo "Missing variable: ${key}"; exit 1; }
done

echo "All required GitHub secrets/variables are present."
```

### Step 5: Trigger and verify release workflows/pipeline progression

```bash
export CODEPIPELINE_NAME="$(aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${PROJECT}-${APPLICATION}-nova-ci-cd" \
  --query "Stacks[0].Outputs[?OutputKey=='PipelineName'].OutputValue | [0]" \
  --output text)"

gh workflow run "Release Plan" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main
PLAN_RUN_ID="$(gh run list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --workflow "Release Plan" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "${PLAN_RUN_ID}" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --exit-status

gh workflow run "Apply Release Plan" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main
APPLY_RUN_ID="$(gh run list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --workflow "Apply Release Plan" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "${APPLY_RUN_ID}" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --exit-status

gh workflow run "Deploy Dev" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --ref main -f pipeline_name="${CODEPIPELINE_NAME}"
DEPLOY_RUN_ID="$(gh run list --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --workflow "Deploy Dev" --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "${DEPLOY_RUN_ID}" --repo "${GITHUB_OWNER}/${GITHUB_REPO}" --exit-status

kubectl rollout status "deployment/${API_DEPLOYMENT_NAME}" -n "${NAMESPACE}"
kubectl get pods -l "app=${APP_LABEL}" -n "${NAMESPACE}"
```

Runbook: `docs/plan/release/release-promotion-dev-to-prod-guide.md`

Pipeline dashboard:
`https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows`

## Acceptance checks

1. Release signing and workflow auth are valid.
2. Pipeline completes Dev -> ManualApproval -> Prod in order.
3. `IMAGE_DIGEST` continuity is preserved Dev to Prod.
4. Evidence links are added to release docs/plan artifacts.

## References

- [documentation-index.md](documentation-index.md)
- [governance-lock-runbook.md](governance-lock-runbook.md)
- [troubleshooting-and-break-glass-guide.md](troubleshooting-and-break-glass-guide.md)
