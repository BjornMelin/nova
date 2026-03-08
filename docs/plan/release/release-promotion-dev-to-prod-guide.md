# Release Promotion Dev-to-Prod Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-03

## Purpose

Execute and audit a full Dev to Prod promotion using immutable artifacts from
one signed source revision.

## Prerequisites

1. `nova-ci-cd` pipeline deployed and source integration active.
2. Release workflows passing in `3M-Cloud/nova` on `main`.
3. Operator permissions to approve CodePipeline manual approval actions.
4. Access to CloudWatch/CodeBuild logs for evidence capture.

## Preconditions

1. Release commit is signed and verified.
2. CodeConnections status is `AVAILABLE`.
3. Pipeline build stage exports required variables:
   - `IMAGE_DIGEST`
   - `PUBLISHED_PACKAGES`
   - `RELEASE_MANIFEST_SHA256`

## Inputs

- `${AWS_REGION}`
- `${CODEPIPELINE_NAME}`
- `${PIPELINE_EXECUTION_ID}`
- `${MANIFEST_SHA256}`
- `${CHANGED_UNITS_JSON}`
- `${VERSION_PLAN_JSON}`
- `${PROMOTION_CANDIDATES_JSON}`

## Promotion procedure

1. Confirm latest pipeline execution and capture execution ID.

    ```bash
    aws codepipeline list-pipeline-executions \
      --region "${AWS_REGION}" \
      --pipeline-name "${CODEPIPELINE_NAME}" \
      --max-results 5

    PIPELINE_EXECUTION_ID="$(aws codepipeline list-pipeline-executions \
      --region "${AWS_REGION}" \
      --pipeline-name "${CODEPIPELINE_NAME}" \
      --max-results 1 \
      --query 'pipelineExecutionSummaries[0].pipelineExecutionId' \
      --output text)"
    ```

2. Wait for `DeployDev` and `ValidateDev` to succeed.

    ```bash
    aws codepipeline get-pipeline-state \
      --region "${AWS_REGION}" \
      --name "${CODEPIPELINE_NAME}"
    ```

3. Execute `Promote Prod` workflow dispatch with:

   - `pipeline_name`
   - `manifest_sha256` from `codeartifact-gate-report.json`
   - `changed_units_json` from staged gate artifact (`changed-units.json`)
   - `version_plan_json` from staged gate artifact (`version-plan.json`)
   - `promotion_candidates_json` from `codeartifact-promotion-candidates.json`

4. Workflow re-runs `scripts.release.codeartifact_gate` using provided inputs,
   validates manifest digest + package namespace/version policy, verifies
   promotion-candidate payload integrity, then promotes package versions from
   staging to prod using `copy-package-versions`.
   Scoped npm candidates carry their namespace explicitly and are promoted with
   `--namespace` plus the unscoped package component.

5. Confirm `DeployProd` and `ValidateProd` complete successfully.

## CodeDeploy blue/green promotion verification (Batch B1)

After `DeployDev` and `DeployProd`, verify CodeDeploy deployment-group controls:

```bash
aws deploy get-deployment-group \
  --region "${AWS_REGION}" \
  --application-name "${CODEDEPLOY_APPLICATION_NAME}" \
  --deployment-group-name "${CODEDEPLOY_DEPLOYMENT_GROUP_NAME}" \
  --query 'deploymentGroupInfo.{deploymentStyle:deploymentStyle,alarmConfiguration:alarmConfiguration,autoRollback:autoRollbackConfiguration,ready:blueGreenDeploymentConfiguration.deploymentReadyOption}'
```

Acceptance:

- `deploymentStyle.deploymentType` = `BLUE_GREEN`
- alarm configuration is enabled with rollback alarms bound
- auto rollback includes `DEPLOYMENT_FAILURE`, `DEPLOYMENT_STOP_ON_ALARM`, and `DEPLOYMENT_STOP_ON_REQUEST`
- deployment ready option uses timeout action `STOP_DEPLOYMENT` for readiness enforcement

## Immutable artifact continuity check

Use CodePipeline action execution details and confirm the same digest is used
for both deployments.

```bash
aws codepipeline list-action-executions \
  --region "${AWS_REGION}" \
  --pipeline-name "${CODEPIPELINE_NAME}" \
  --filter pipelineExecutionId="${PIPELINE_EXECUTION_ID}"
```

Acceptance:

- `IMAGE_DIGEST` in Build output equals digest used by both Dev and Prod
  CloudFormation actions.
- No rebuild occurs after manual approval.

## Evidence to store

1. release plan workflow URL
2. release apply workflow URL
3. verify signature workflow URL
4. pipeline execution ID
5. manifest digest used for package promotion gate
6. package promotion candidates JSON
7. manual approver and timestamp
8. digest continuity evidence
9. validation logs for `/v1/health/live`, `/v1/health/ready`,
   `/metrics/summary`

Store links in:

- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- `docs/plan/release/evidence-log.md`

## References

- CodePipeline manual approvals:
  <https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-action-add.html>
- CodePipeline list-action-executions API:
  <https://docs.aws.amazon.com/cli/latest/reference/codepipeline/list-action-executions.html>
