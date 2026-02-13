# Non-Prod Live Validation Runbook

Status: Pending external execution
Owner: Release Architecture + Platform Operations
Last updated: 2026-02-12

## 1. Purpose

Provide a single operator runbook for the remaining release-blocking,
AWS-live validations that cannot be proven by local repository checks.

## 2. Blocking Gates Covered

- Sidecar ALB routing and health-check behavior in non-prod AWS.
- Cross-repo E2E flow:
  browser upload -> jobs enqueue -> worker result -> download.
- CloudWatch dashboards and alarm behavior under synthetic failure.

## 3. Preconditions

- `nova` runtime build is deployed to non-prod.
- `container-craft` stack changes for split routes are deployed to non-prod.
- `dash-pca` non-prod points to split API routes.
- AWS CLI credentials target the non-prod account/region.

## 4. Required Inputs

- `NONPROD_API_BASE_URL` (for example, `https://<host>`).
- `NONPROD_DASH_URL` (dash-pca non-prod URL).
- `AWS_REGION`.
- `ECS_CLUSTER`.
- `ECS_SERVICE`.
- `ALB_TARGET_GROUP_ARN`.
- `DASHBOARD_NAME` (CloudWatch dashboard for this service).
- `ALARM_NAMES` (space-separated alarm names to validate).

## 5. Gate A: ALB Routing and Health

### A1. Basic route reachability (must not be 404)

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
- Transfer/job routes return a contract response (`401/403/422/400` allowed),
  but never `404`.

### A2. ECS and target-group health

```bash
aws ecs describe-services \
  --region "${AWS_REGION}" \
  --cluster "${ECS_CLUSTER}" \
  --services "${ECS_SERVICE}" \
  --query "services[0].{running:runningCount,pending:pendingCount,events:events[0:5]}"

aws elbv2 describe-target-health \
  --region "${AWS_REGION}" \
  --target-group-arn "${ALB_TARGET_GROUP_ARN}" \
  --query "TargetHealthDescriptions[].TargetHealth.State"
```

Acceptance:

- ECS service stabilizes with expected running task count.
- Target health states converge to `healthy` without repeated flapping.

## 6. Gate B: Cross-Repo E2E Smoke

### B1. Browser upload and async completion

1. Open `NONPROD_DASH_URL`.
2. Upload a supported file (`.csv` or `.xlsx`) using the async uploader.
3. Confirm `jobs/enqueue` is called and a `job_id` is returned.
4. Confirm polling reaches terminal `succeeded`.
5. Confirm generated output/download path works.

Acceptance:

- Upload flow completes without manual backend intervention.
- No legacy route usage appears in browser/network traces.
- Correlated request IDs exist across app logs for the same flow.

## 7. Gate C: Dashboard and Alarm Validation

### C1. Dashboard data presence

```bash
aws cloudwatch get-dashboard \
  --region "${AWS_REGION}" \
  --dashboard-name "${DASHBOARD_NAME}" \
  --query "DashboardValidationMessages"
```

Acceptance:

- Dashboard has no validation errors.
- Widgets show current datapoints for traffic/error/latency and queue lag.

### C2. Alarm validation under synthetic failure

Use one controlled method:

1. Metric-driven synthetic failure in non-prod traffic.
2. CloudWatch `set-alarm-state` dry validation for notification wiring.

Record exact method and evidence for each alarm in `ALARM_NAMES`.

Acceptance:

- Each targeted alarm reaches ALARM state once during validation.
- Expected notification path is observed.
- Alarms return to OK after synthetic condition is removed.

## 8. Evidence Capture Template

For each gate, capture:

- execution date/time (UTC)
- operator
- command/log artifact link
- pass/fail
- remediation notes (if failed)

Store evidence links in:

- `FINAL-PLAN.md`
- `docs/plan/PLAN.md`
- `docs/plan/subplans/SUBPLAN-0005.md`
