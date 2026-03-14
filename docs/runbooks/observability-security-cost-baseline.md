# Observability, Security, and Cost Baseline (ADR-0023 + SPEC-0000 + SPEC-0016 + requirements.md)

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
- alarms are consumable by ECS deployment alarms and ECS-native blue/green
  rollback settings

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

## Cost-emergency near-zero posture

Canonical runtime convergence (`scripts/release/deploy-runtime-cloudformation-environment.sh`)
now requires `RUNTIME_COST_MODE`:

- `standard`: prod-safe baseline (`API_TASK_CPU=2048`, `API_TASK_MEMORY=8192`,
  `API_DESIRED_COUNT=2`, `OBSERVABILITY_MIN_TASK_COUNT=2`)
- `saver`: low-cost active posture (`API_TASK_CPU=512`, `API_TASK_MEMORY=1024`,
  `API_DESIRED_COUNT=1`, `OBSERVABILITY_MIN_TASK_COUNT=1`,
  `OBSERVABILITY_MAX_TASK_COUNT=2`)
- `paused`: near-zero runtime posture (`API_DESIRED_COUNT=0`,
  `OBSERVABILITY_ENABLED=false`, `ENABLE_WORKER=false`)

When runtime availability can be sacrificed to stop spend immediately, use
`RUNTIME_COST_MODE=paused` and converge both `dev` and `prod`.

If `CacheUrlSecretArn` rotates to a new secret value under the same ARN, force
a new ECS deployment after rotation so running tasks reload `CACHE_REDIS_URL`.
Without a forced deployment, existing tasks keep the previous secret value.

## Cost hook

`MonthlyEstimatedChargesAlarm` (`AWS/Billing EstimatedCharges`) is the baseline hook.

Prerequisites before rollout:

- deploy/evaluate this alarm in `us-east-1` (`Condition: IsUsEast1`)
- enable account-level CloudWatch billing alerts in Billing Preferences
- allow approximately 15 minutes after enabling billing alerts for metric publication

`AlarmActionArn` should route to SNS/Lambda escalation targets aligned with org
budget response policy.

References:

- Enable billing alerts + region requirement:
  https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/gs_monitor_estimated_charges_with_cloudwatch.html
- AWS Billing alarm troubleshooting examples:
  https://repost.aws/knowledge-center/cloudwatch-estimatedcharges-alarm

If/when account-level `AWS::Budgets::Budget` ownership is standardized in this repo, this alarm remains the mandatory service-level threshold hook.


### Batch B1 ECS-native deployment binding contract

When `infra/runtime/ecs/service.yml` runs with ECS-native blue/green enabled,
bind these rollback alarm inputs:

- `DeploymentRollbackAlarmNamePrimary`
- `DeploymentRollbackAlarmNameSecondary`

Recommended source of alarm names is `DeploymentRollbackAlarmNamesCsv` from
`infra/runtime/observability/ecs-observability-baseline.yml` (split into primary/secondary in pipeline/env config).
