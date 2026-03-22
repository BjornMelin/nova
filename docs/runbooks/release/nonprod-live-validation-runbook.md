# Non-Prod Live Validation Runbook

Status: Active
Owner: Release Architecture + Platform Operations
Last updated: 2026-03-19

## When to use this vs browser checklist

- **This runbook (NONPROD):** AWS-live integration--CodeConnections, ALB,
  CodePipeline/CodeBuild, CloudWatch, cross-repo flows against real accounts.
- **[browser-live-validation-checklist.md](browser-live-validation-checklist.md):**
  Deterministic browser/`agent-browser` checks against `DASH_BASE_URL` and
  `NOVA_BASE_URL` (route contract + UI smoke). Use both where applicable.

Some checklist items at the end still depend on **non-prod AWS access** and
stack health; treat unchecked boxes there as environment backlog, not doc drift.

## 1. Purpose

Provide one operator runbook for release-blocking, AWS-live validation gates
that cannot be fully proven by local checks.

Related setup sequence:

- [`Runbooks index`](../README.md)
- [`nova-cicd-end-to-end-deploy.md`](../provisioning/nova-cicd-end-to-end-deploy.md)
- [`release-promotion-dev-to-prod.md`](release-promotion-dev-to-prod.md)
- [`browser-live-validation-checklist.md`](browser-live-validation-checklist.md)

## 2. Blocking gates covered

- CodeConnections activation and source event readiness.
- Sidecar ALB routing and health-check behavior in non-prod AWS.
- Cross-repo E2E flow:
  browser upload -> jobs enqueue -> worker result -> download.
- CloudWatch dashboards and alarm behavior under synthetic failure.
- Dev to Prod manual gate behavior in CodePipeline.

## 3. Preconditions

- `nova` runtime build is deployed to non-prod.
- Nova CI/CD stack changes from `infra/nova/**` are deployed from this repository.
- `dash-pca` non-prod points to canonical `/v1/*` capability routes.
- AWS CLI credentials target the non-prod account/region.

## 4. Required inputs

- `NONPROD_API_BASE_URL`
- `NONPROD_DASH_URL`
- `AWS_REGION`
- `ECS_CLUSTER`
- `ECS_SERVICE`
- `ALB_TARGET_GROUP_BLUE_ARN`
- `ALB_TARGET_GROUP_GREEN_ARN`
- `DASHBOARD_NAME`
- `ALARM_NAMES`
- `CODEPIPELINE_NAME`
- `CODECONNECTION_ARN`

## 5. Gate A: CodeConnections and source integration

### A1. Connection activation status

```bash
aws codeconnections get-connection \
  --region "${AWS_REGION}" \
  --connection-arn "${CODECONNECTION_ARN}" \
  --query "Connection.ConnectionStatus"
```

Acceptance:

- Status is `AVAILABLE` (not `PENDING`).

### A2. Source event reaches pipeline

```bash
aws codepipeline list-pipeline-executions \
  --region "${AWS_REGION}" \
  --pipeline-name "${CODEPIPELINE_NAME}" \
  --max-results 5
```

Acceptance:

- Latest signed release commit appears as source revision in execution history.

## 6. Gate B: ALB routing and health

### B1. Basic route reachability

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  "${NONPROD_API_BASE_URL}/v1/health/live"
curl -sS -o /dev/null -w "%{http_code}\n" \
  "${NONPROD_API_BASE_URL}/v1/health/ready"
curl -sS -o /dev/null -w "%{http_code}\n" \
  -X POST "${NONPROD_API_BASE_URL}/v1/transfers/uploads/initiate" \
  -H "Content-Type: application/json" -d '{}'
curl -sS -o /dev/null -w "%{http_code}\n" \
  -X POST "${NONPROD_API_BASE_URL}/v1/jobs" \
  -H "Content-Type: application/json" -d '{}'
curl -sS -o /dev/null -w "%{http_code}\n" \
  "${NONPROD_API_BASE_URL}/v1/jobs/nonprod-smoke/events"
curl -sS -o /dev/null -w "%{http_code}\n" \
  "${NONPROD_API_BASE_URL}/v1/capabilities"
curl -sS -o /dev/null -w "%{http_code}\n" \
  "${NONPROD_API_BASE_URL}/metrics/summary"
```

Acceptance:

- `/v1/health/live` is `200`.
- `/v1/health/ready` is `200`.
- `/v1/transfers/uploads/initiate` returns contract responses
  (`401/403/409/422/503` allowed), but never `404`.
- Canonical `/v1/jobs*`, `/v1/health/live`, `/v1/health/ready`, and
  `/v1/capabilities` routes return contract responses (non-`404`) during
  dry-run checks.
- `/metrics/summary` returns a contract response (non-`404`) during dry-run
  checks.
- Commands and runbook notes use only canonical `/v1/*` routes and
  `/metrics/summary`.

### B2. ECS and target-group health

```bash
aws ecs describe-services \
  --region "${AWS_REGION}" \
  --cluster "${ECS_CLUSTER}" \
  --services "${ECS_SERVICE}" \
  --query "services[0].{running:runningCount,pending:pendingCount,events:events[0:5]}"

aws elbv2 describe-target-health \
  --region "${AWS_REGION}" \
  --target-group-arn "${ALB_TARGET_GROUP_BLUE_ARN}" \
  --query "TargetHealthDescriptions[].TargetHealth.State"
```

Acceptance:

- ECS service stabilizes with expected running task count.
- Target states converge to `healthy` without persistent flapping.

### B3. ECS-native blue/green authority and readiness gating

```bash
aws ecs describe-services \
  --region "${AWS_REGION}" \
  --cluster "${ECS_CLUSTER}" \
  --services "${ECS_SERVICE}" \
  --query "services[0].{deployments:deployments,alarms:deploymentConfiguration.alarms}"

aws elbv2 describe-target-health \
  --region "${AWS_REGION}" \
  --target-group-arn "${ALB_TARGET_GROUP_BLUE_ARN}" \
  --query "TargetHealthDescriptions[].TargetHealth.State"

aws elbv2 describe-target-health \
  --region "${AWS_REGION}" \
  --target-group-arn "${ALB_TARGET_GROUP_GREEN_ARN}" \
  --query "TargetHealthDescriptions[].TargetHealth.State"
```

Acceptance:

- ECS service uses blue/green traffic shifting with the expected active and
  alternate target groups.
- Deployment alarms are enabled with expected alarm names.
- Green target group reaches healthy state before production traffic shift.

## 7. Gate C: Cross-repo E2E smoke

Use the deterministic execution contract in
[`browser-live-validation-checklist.md`](browser-live-validation-checklist.md)
for command-level browser validation and artifact capture.

### C1. Browser upload and async completion

1. Open `NONPROD_DASH_URL`.
2. Upload supported file (`.csv` or `.xlsx`) via async uploader.
3. Confirm `POST /v1/jobs` is called and `job_id` is returned.
4. Confirm polling reaches terminal `succeeded`.
5. Confirm generated output/download path works.

Acceptance:

- Flow completes without manual backend intervention.
- No legacy route usage appears in browser/network traces.
- Correlated request IDs exist across logs for the same flow.

## 8. Gate D: Dashboard and alarm validation

### D1. Dashboard data presence

```bash
aws cloudwatch get-dashboard \
  --region "${AWS_REGION}" \
  --dashboard-name "${DASHBOARD_NAME}" \
  --query "DashboardValidationMessages"
```

Acceptance:

- Dashboard has no validation errors.
- Widgets show current datapoints for traffic/error/latency and queue lag.

### D2. Alarm validation under synthetic failure

Use one controlled method:

1. Metric-driven synthetic failure in non-prod traffic.
2. CloudWatch `set-alarm-state` dry validation for notification wiring.

Acceptance:

- Each targeted alarm reaches ALARM once.
- Expected notification path is observed.
- Alarms return to OK after synthetic condition is removed.

## 9. Gate E: Promotion control validation

1. Execute non-prod CodePipeline run through ValidateDev.
2. Confirm pipeline pauses at ManualApproval.
3. Confirm unapproved runs cannot proceed to Prod.
4. Approve manually and confirm Prod stages execute.

Acceptance:

- Manual approval gate is enforced and auditable.
- Prod runs only after explicit approval.

## 10. Evidence capture template

For each gate capture:

- execution date/time (UTC)
- operator
- command/log artifact link
- pass/fail
- remediation notes (if failed)

Record outcomes with durable pointers (for example GitHub Actions run URLs,
pipeline execution IDs, and object-storage URIs for JSON bundles) and attach
them to the promotion PR or change record per
[`release-policy.md`](release-policy.md) §6--do not maintain a separate log file
under `docs/`.

## 11. Access prerequisites and rollback

Before running gates A-E, ensure Batch B validation read access exists (see:
`docs/runbooks/release/troubleshooting-and-break-glass.md#batch-b-validation-read-access`).

Rollback (IAM): set `BatchBOperatorPrincipalArn` to empty string and update the
IAM stack to remove `BatchBValidationOperatorRole`.
