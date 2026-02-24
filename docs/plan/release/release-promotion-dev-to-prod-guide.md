# Release Promotion Dev-to-Prod Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

Execute and audit a full Dev to Prod promotion using immutable artifacts from
one signed source revision.

## Prerequisites

1. `nova-ci-cd` pipeline deployed and source integration active.
2. Release workflows passing in `BjornMelin/nova` on `main`.
3. Operator permissions to approve CodePipeline manual approval actions.
4. Access to CloudWatch/CodeBuild logs for evidence capture.

## Preconditions

1. Release commit is signed and verified.
2. CodeConnections status is `AVAILABLE`.
3. Pipeline build stage exports required variables:
   - `IMAGE_DIGEST`
   - `PUBLISHED_PACKAGES`
   - `RELEASE_MANIFEST_SHA256`

## Promotion procedure

1. Confirm latest pipeline execution and capture execution ID.

    ```bash
    aws codepipeline list-pipeline-executions \
      --region "${AWS_REGION}" \
      --pipeline-name "${CODEPIPELINE_NAME}" \
      --max-results 5
    ```

2. Wait for `DeployDev` and `ValidateDev` to succeed.

    ```bash
    aws codepipeline get-pipeline-state \
      --region "${AWS_REGION}" \
      --name "${CODEPIPELINE_NAME}"
    ```

3. Manual approval step.

   - Open CodePipeline execution in console.
   - Review Build and ValidateDev evidence.
   - Approve promotion with reason text and ticket reference.

4. Confirm `DeployProd` and `ValidateProd` complete successfully.

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
5. manual approver and timestamp
6. digest continuity evidence
7. validation logs for `/healthz`, `/readyz`, `/metrics/summary`

Store links in:

- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- `docs/plan/PLAN.md`
- `FINAL-PLAN.md`

## References

- CodePipeline manual approvals:
  <https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-action-add.html>
- CodePipeline list-action-executions API:
  <https://docs.aws.amazon.com/cli/latest/reference/codepipeline/list-action-executions.html>
