# Release Promotion Dev-to-Prod Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-05

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
   - `FILE_IMAGE_DIGEST`
   - `AUTH_IMAGE_DIGEST`
   - `PUBLISHED_PACKAGES`
   - `RELEASE_MANIFEST_SHA256`

`RELEASE_MANIFEST_SHA256` is the SHA256 of
`docs/plan/release/RELEASE-VERSION-MANIFEST.md`.

## Inputs

- `${AWS_REGION}`
- `${CODEPIPELINE_NAME}`
- `${PIPELINE_EXECUTION_ID}`
- `${MANIFEST_SHA256}`
- `${CHANGED_UNITS_JSON}`
- `${VERSION_PLAN_JSON}`
- `${PROMOTION_CANDIDATES_JSON}`
- `${ECS_CLUSTER}`
- `${ECS_SERVICE}`
- `${PUBLIC_ALB_WEB_ACL_ARN}` (when ALB is internet-facing)

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
   - `manifest_sha256` equal to `RELEASE_MANIFEST_SHA256`
     (`SHA256(docs/plan/release/RELEASE-VERSION-MANIFEST.md)`);
     `codeartifact-gate-report.json` may carry this value but is not the
     authority itself
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

## ECS-native blue/green promotion verification

After `DeployDev` and `DeployProd`, verify ECS-native service deployment
controls:

```bash
aws ecs describe-services \
  --region "${AWS_REGION}" \
  --cluster "${ECS_CLUSTER}" \
  --services "${ECS_SERVICE}" \
  --query 'services[0].{deploymentController:deploymentController,deploymentConfiguration:deploymentConfiguration,loadBalancers:loadBalancers}'
```

Acceptance:

- `deploymentController.type` is `ECS`
- `deploymentConfiguration.strategy` is `BLUE_GREEN`
- deployment alarms are enabled with rollback alarms bound
- the service load balancer configuration references primary and alternate
  target groups plus `EcsInfrastructureRoleArn`

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

- `FILE_IMAGE_DIGEST` in Build output equals digest used by both Dev and Prod
  file-service CloudFormation actions.
- `AUTH_IMAGE_DIGEST` in Build output equals digest used by both Dev and Prod
  auth-service CloudFormation actions.
- No rebuild occurs after manual approval.

## Evidence to store

1. release plan workflow URL
2. release apply workflow URL
3. verify signature workflow URL
4. pipeline execution ID
5. manifest digest used for package promotion gate
6. package promotion candidates JSON
7. manual approver and timestamp
8. digest continuity evidence for file and auth images
9. validation logs for `/v1/health/live`, `/v1/health/ready`,
   `/metrics/summary`, `/v1/token/verify`, and `/v1/token/introspect`
10. WAF evidence for any internet-facing ALB (`PublicAlbWebAclArn`)

Store links in:

- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- `docs/plan/release/evidence-log.md`

## References

- CodePipeline manual approvals:
  <https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-action-add.html>
- CodePipeline list-action-executions API:
  <https://docs.aws.amazon.com/cli/latest/reference/codepipeline/list-action-executions.html>
