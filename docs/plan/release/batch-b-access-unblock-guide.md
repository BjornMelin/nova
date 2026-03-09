# Batch B Access Unblock Guide

Status: Implemented in IaC (pending stack apply)
Owner: Platform Engineering + Operations
Last updated: 2026-03-02

## Purpose

Provide the minimal access changes and fallback evidence procedure required to
close Batch B governance and non-prod live validation gates.

## Prerequisites

1. Release stack operator role is deployable with `BatchBOperatorPrincipalArn`.
2. `aws` CLI and `gh` CLI are authenticated.
3. AWS `codepipeline:GetPipelineState` scope is expected to include the target pipeline pattern `${Project}-${Application}-*`.

## Inputs

- `${PROJECT}` (default `nova`)
- `${APPLICATION}` (default `ci`)
- `${BATCHB_VALIDATION_ROLE_NAME}` (default `${PROJECT}-${APPLICATION}-batch-b-validation-operator-role`)

## Acceptance checks

- Confirm the Batch B validation role exists and can be assumed by the operator
  principal ARN.
- Verify the denied read actions from the evidence log are now allowed:
  `codeconnections:GetConnection`, `codepipeline:ListPipelineExecutions`,
  `codepipeline:ListPipelines`, and `codedeploy:ListApplications`.
- Re-run `docs/plan/release/governance-lock-runbook.md` gates and confirm no new
  failures are introduced.

## 1) AWS IAM read access delta (minimum)

Use the Nova IaC-defined Batch B validation operator role in `infra/nova/nova-iam-roles.yml` by setting `BatchBOperatorPrincipalArn` on stack apply/update.

Observed denied actions:

- `codeconnections:GetConnection`
- `codepipeline:ListPipelineExecutions`
- `codepipeline:ListPipelines`
- `ecs:DescribeServices`

Required for full runbook execution (A-E gates):

- CodeConnections: `GetConnection`
- CodePipeline: `ListPipelines`, `ListPipelineExecutions`, `GetPipelineState`, `GetPipelineExecution`
- ECS: `DescribeServices`, `ListClusters`, `ListServices`
- ELBv2: `DescribeTargetHealth`, `DescribeTargetGroups`, `DescribeLoadBalancers`
- CloudWatch: `GetDashboard`, `DescribeAlarms`, `GetMetricData`, `ListDashboards`

### IaC policy source of truth

Use `infra/nova/nova-iam-roles.yml` as the canonical policy definition for the
operator role. Do not apply the JSON below as a full production policy.

### Illustrative IAM policy scaffold (approximate summary)

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

## Step-by-step commands

- Capture stack outputs and ensure role ARN is available.
- Use the verified role for all Batch B validation checks.

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
   - `docs/plan/release/evidence-log.md`



## 4) Apply / verify / rollback

### Apply

1. Update/apply the `infra/nova/nova-iam-roles.yml` stack with:
   - `BatchBOperatorPrincipalArn=<trusted-principal-arn>`
2. Capture stack output `BatchBValidationOperatorRoleArn`.
3. Assume that role for Batch B gate execution.

### Verify

From an assumed session for `BatchBValidationOperatorRoleArn`, verify at minimum:

- `aws codeconnections get-connection --connection-arn <arn>`
- `aws codepipeline list-pipelines`
- `aws codepipeline list-pipeline-executions --pipeline-name <name>`
- `aws codedeploy list-applications`

### Rollback

- Set `BatchBOperatorPrincipalArn` back to empty string and update stack.
- Confirm `BatchBValidationOperatorRoleArn` output is absent.
- Re-run IAM verification to confirm access removed.

## References

- [documentation-maintenance-guide.md](documentation-maintenance-guide.md)
- [gov lock runbook](governance-lock-runbook.md)
- [NONPROD live validation runbook](NONPROD-LIVE-VALIDATION-RUNBOOK.md)
