# Non-Prod Live Validation Runbook

Status: Pending external execution
Owner: Release Architecture + Platform Operations
Last updated: 2026-03-02

Transition note (2026-03-02): Commands in this runbook validate the current
implemented baseline routes (`/api/*`, `/healthz`, `/readyz`). Target-state
validation commands for `/v1/*` will be added in the next implementation
branch when `SPEC-0015` moves from planned to active.

## 1. Purpose

Provide one operator runbook for release-blocking, AWS-live validation gates
that cannot be fully proven by local checks.

Related setup sequence:

- `documentation-index.md`
- `deploy-nova-cicd-end-to-end-guide.md`
- `release-promotion-dev-to-prod-guide.md`

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
- `dash-pca` non-prod points to split API routes.
- AWS CLI credentials target the non-prod account/region.

## 4. Required inputs

- `NONPROD_API_BASE_URL`
- `NONPROD_DASH_URL`
- `AWS_REGION`
- `ECS_CLUSTER`
- `ECS_SERVICE`
- `ALB_TARGET_GROUP_BLUE_ARN`
- `ALB_TARGET_GROUP_GREEN_ARN`
- `CODEDEPLOY_APPLICATION_NAME`
- `CODEDEPLOY_DEPLOYMENT_GROUP_NAME`
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
  "${NONPROD_API_BASE_URL}/healthz"
curl -sS -o /dev/null -w "%{http_code}\n" \
  "${NONPROD_API_BASE_URL}/readyz"
curl -sS -o /dev/null -w "%{http_code}\n" \
  -X POST "${NONPROD_API_BASE_URL}/api/transfers/uploads/initiate" \
  -H "Content-Type: application/json" -d '{}'
curl -sS -o /dev/null -w "%{http_code}\n" \
  -X POST "${NONPROD_API_BASE_URL}/api/jobs/enqueue" \
  -H "Content-Type: application/json" -d '{}'
```

Acceptance:

- `/healthz` is `200`.
- `/readyz` is `200`.
- Transfer/job routes return contract responses (`401/403/422/400` allowed),
  but never `404`.

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

### B3. CodeDeploy blue/green authority and readiness gating

```bash
aws deploy get-deployment-group \
  --region "${AWS_REGION}" \
  --application-name "${CODEDEPLOY_APPLICATION_NAME}" \
  --deployment-group-name "${CODEDEPLOY_DEPLOYMENT_GROUP_NAME}" \
  --query "deploymentGroupInfo.{deploymentStyle:deploymentStyle,blueGreen:blueGreenDeploymentConfiguration,alarmConfiguration:alarmConfiguration,autoRollback:autoRollbackConfiguration}"

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

- Deployment style is blue/green with traffic control.
- Alarm rollback configuration is enabled with expected alarm names.
- Auto rollback includes deployment failure + stop-on-alarm + stop-on-request.
- Green target group reaches healthy state before production traffic shift.

## 7. Gate C: Cross-repo E2E smoke

### C1. Browser upload and async completion

1. Open `NONPROD_DASH_URL`.
2. Upload supported file (`.csv` or `.xlsx`) via async uploader.
3. Confirm `jobs/enqueue` is called and `job_id` is returned.
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

Store evidence links in:

- `FINAL-PLAN.md`
- `docs/plan/PLAN.md`
- `docs/plan/subplans/SUBPLAN-0005.md`


## 11. Latest execution status (2026-03-02)

Evidence directory:

- `docs/plan/release/evidence/nonprod-validation/20260302T231233Z`

Executed from authenticated CLI session:

- `aws sts get-caller-identity` (passed)
- `aws cloudformation describe-stacks` for `nova-ci-nova-ci-cd` and
  `nova-ci-nova-dev` (passed; used to confirm pipeline/connection metadata)

Blocked by IAM authorization in current operator role:

- `codeconnections:GetConnection`
- `codepipeline:ListPipelineExecutions`
- additional service-level reads required for full Gate B-D verification

Impact:

- Gates A-E cannot be marked complete from this session due to missing read
  permissions and missing non-prod runtime endpoint inputs.

Required follow-up:

1. Grant/assume an operator role with read access to CodeConnections,
   CodePipeline, CodeDeploy, ECS, ELBv2, and CloudWatch for non-prod.
2. Provide/confirm values for required runbook inputs (API/Dash URL, ECS service,
   target groups, deployment group, dashboard, alarms).
3. Re-run gates A-E and append pass/fail evidence artifacts in this runbook.

Reference:

- `docs/plan/release/batch-b-access-unblock-guide.md`
