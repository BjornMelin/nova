# Observability, Security, and Cost Baseline (ADR-0015 / SPEC-0015)

This runbook is the production authority for Batch A4 (blueprint Batch 5 hardening scope):

- SLO-linked rollback alarms for ECS/ALB deploys
- environment-specific log retention
- API service dashboard (latency/error/cpu/memory/5xx)
- explicit OIDC trust-policy constraints for GitHub Actions
- baseline right-sizing/autoscaling envelopes and budget alarm hooks

## Canonical IaC

- `infra/runtime/observability/ecs-observability-baseline.yml`
- `infra/nova/nova-iam-roles.yml`

## Deployment rollback / SLO alarms

Use `DeploymentRollbackAlarmNamesCsv` from `ecs-observability-baseline.yml` as the alarm input for deployment rollback controls.

Alarm set:

- `ApiLatencyP95RollbackAlarm` (ALB `TargetResponseTime` p95 in ms)
- `Api5xxErrorRateRollbackAlarm` (ALB target 5xx % via metric math)

Design intent:

- alarms are tuned to SLO breach conditions, not only hard infrastructure failures
- alarms are consumable by ECS deployment alarms and CodeDeploy stop/rollback settings

AWS references:

- ECS deployment alarms/failure detection: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-alarm-failure.html
- CloudFormation deployment alarms on `AWS::ECS::Service`: https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ecs-service-deploymentalarms

## Log retention policy tiers

Log group retention is environment constrained:

- `dev`: 30 days
- `prod`: 90 days

Configured by `ServiceLogRetentionPolicy` in `ecs-observability-baseline.yml` when
`ManageLogGroupRetentionPolicy=true`.

Default is `false` to avoid cross-stack ownership conflicts when the ECS service
stack already owns the log group.

## Dashboard baseline

`ServiceObservabilityDashboard` includes:

- ALB `TargetResponseTime` p95
- ALB `HTTPCode_Target_5XX_Count`
- ECS `CPUUtilization`
- ECS `MemoryUtilization`

This is the minimum required release gate dashboard for API deployment evidence.

## OIDC trust-policy constraints (fail-closed)

`infra/nova/nova-iam-roles.yml` enforces:

- provider: `token.actions.githubusercontent.com`
- audience constraint: `token.actions.githubusercontent.com:aud: sts.amazonaws.com`
- subject constraint (repo + branch scope):
  - `repo:${RepositoryOwner}/${RepositoryName}:ref:refs/heads/${MainBranchName}`

No wildcard `sub` patterns are allowed for release role assumption.

Authority references:

- GitHub OIDC on AWS: https://docs.github.com/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services
- AWS OIDC trust controls: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_oidc_secure-by-default.html

## Right-sizing and autoscaling envelope (baseline)

Default baseline in `ecs-observability-baseline.yml`:

- `MinTaskCount`: 2
- `MaxTaskCount`: 20
- target tracking CPU: 60%
- target tracking memory: 70%

Operational guidance:

- start with `TaskCpu`/`TaskMemory` from current service profile
- tune scale targets only after 7-day p95 and saturation review
- do not lower `MinTaskCount` to 1 in prod except explicit exception with incident/risk note

## Cost hook

`MonthlyEstimatedChargesAlarm` (`AWS/Billing EstimatedCharges`) is the baseline hook.

This alarm is conditionally created only in `us-east-1` (`Condition: IsUsEast1`)
because AWS Billing metrics are region-scoped to `us-east-1` for standard account
telemetry.

Use `AlarmActionArn` for SNS/Lambda escalation and connect to org-level budget process.

If/when account-level `AWS::Budgets::Budget` ownership is standardized in this repo, this alarm remains the mandatory service-level threshold hook.
