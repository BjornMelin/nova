# Batch B Access Unblock Guide

Status: Action-required
Owner: Platform Operations
Last updated: 2026-03-02

## Purpose

Provide the minimal access changes and fallback evidence procedure required to
close Batch B governance and non-prod live validation gates.

## 1) AWS IAM read access delta (minimum)

Attach an additional read-only policy (or equivalent permissions) to the role
used for Batch B execution.

Observed denied actions:

- `codeconnections:GetConnection`
- `codepipeline:ListPipelineExecutions`
- `codepipeline:ListPipelines`
- `codedeploy:ListApplications`

Required for full runbook execution (A-E gates):

- CodeConnections: `GetConnection`
- CodePipeline: `ListPipelines`, `ListPipelineExecutions`, `GetPipelineState`, `GetPipelineExecution`
- CodeDeploy: `ListApplications`, `GetDeploymentGroup`, `GetDeployment`
- ECS: `DescribeServices`, `ListClusters`, `ListServices`
- ELBv2: `DescribeTargetHealth`, `DescribeTargetGroups`, `DescribeLoadBalancers`
- CloudWatch: `GetDashboard`, `DescribeAlarms`, `GetMetricData`, `ListDashboards`

### Suggested policy scaffold

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BatchBReadOnlyValidation",
      "Effect": "Allow",
      "Action": [
        "codeconnections:GetConnection",
        "codepipeline:ListPipelines",
        "codepipeline:ListPipelineExecutions",
        "codepipeline:GetPipelineState",
        "codepipeline:GetPipelineExecution",
        "codedeploy:ListApplications",
        "codedeploy:GetDeploymentGroup",
        "codedeploy:GetDeployment",
        "ecs:DescribeServices",
        "ecs:ListClusters",
        "ecs:ListServices",
        "elasticloadbalancing:DescribeTargetHealth",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeLoadBalancers",
        "cloudwatch:GetDashboard",
        "cloudwatch:DescribeAlarms",
        "cloudwatch:GetMetricData",
        "cloudwatch:ListDashboards"
      ],
      "Resource": "*"
    }
  ]
}
```

## 2) GitHub governance evidence fallback (plan-limited repos)

When branch-protection/rules REST endpoints return plan-level `403`, capture
manual evidence via GitHub UI and keep it in the same timestamped evidence
folder.

Required UI captures:

1. Branch protection page for `main` showing:
   - required status checks list
   - strict/up-to-date setting
   - required review settings
   - required conversation resolution
2. CODEOWNERS file view for `main` including commit/blob reference.
3. PR link that merged `.github/CODEOWNERS` (if separate) or proving commit on
   `main` history.

Required file outputs in evidence folder:

- `github-ui-branch-protection-main.png`
- `github-ui-required-checks-main.png`
- `github-ui-codeowners-main.png`
- `github-ui-codeowners-history.png`
- `operator-attestation.md` (date/operator/context)

## 3) Re-run closure sequence

After access updates:

1. Re-run `docs/plan/release/governance-lock-runbook.md` evidence capture.
2. Re-run `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md` Gates A-E.
3. Append pass/fail + artifact paths to:
   - `FINAL-PLAN.md`
   - `docs/plan/PLAN.md`
   - `docs/plan/subplans/SUBPLAN-0005.md`

