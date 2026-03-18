# CodeConnections Activation and Validation Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-17

## Purpose

Activate AWS CodeConnections for the GitHub source integration and validate
that signed release commits trigger pipeline executions.

## Prerequisites

1. AWS CLI v2 configured for the target account and region.
2. `nova-ci-cd` stack deployed and accessible in CloudFormation.
   If the release control plane is in its idle-cost posture, recreate
   `nova-ci-cd` and `nova-codebuild-release` first with
   `./scripts/release/day-0-operator-command-pack.sh`.
3. Permissions for `cloudformation:DescribeStacks`,
   `codeconnections:GetConnection`, and `codepipeline:*read*` APIs.

## Inputs

- `${AWS_REGION}`
- `${PIPELINE_STACK_NAME}` default: `nova-ci-nova-ci-cd`
- `${CODEPIPELINE_NAME}` from stack output
- `${CONNECTION_ARN}` from stack output

## Step-by-step commands

1. Read connection ARN output from the pipeline stack.

    ```bash
    aws cloudformation describe-stacks \
      --region "${AWS_REGION}" \
      --stack-name "${PIPELINE_STACK_NAME}" \
      --query 'Stacks[0].Outputs[?OutputKey==`ConnectionArn`].OutputValue | [0]' \
      --output text
    ```

2. Check connection status.

    ```bash
    aws codeconnections get-connection \
      --region "${AWS_REGION}" \
      --connection-arn "${CONNECTION_ARN}" \
      --query 'Connection.ConnectionStatus' \
      --output text
    ```

3. If status is `PENDING`, activate in AWS Console.

   - Open AWS Developer Tools -> Connections.
   - Select `${CONNECTION_ARN}`.
   - Complete GitHub authorization.
   - Re-run status command until `AVAILABLE`.

4. Validate source events are reaching pipeline.

    ```bash
    aws codepipeline list-pipeline-executions \
      --region "${AWS_REGION}" \
      --pipeline-name "${CODEPIPELINE_NAME}" \
      --max-results 5
    ```

5. Validate latest execution source revision.

    ```bash
    PIPELINE_EXECUTION_ID="$(aws codepipeline list-pipeline-executions \
      --region "${AWS_REGION}" \
      --pipeline-name "${CODEPIPELINE_NAME}" \
      --max-results 1 \
      --query 'pipelineExecutionSummaries[0].pipelineExecutionId' \
      --output text)"

    if [[ -z "${PIPELINE_EXECUTION_ID}" || "${PIPELINE_EXECUTION_ID}" == "None" ]]; then
      echo "No pipeline executions found for ${CODEPIPELINE_NAME}. Trigger a source change and retry." >&2
      exit 1
    fi

    aws codepipeline get-pipeline-execution \
      --region "${AWS_REGION}" \
      --pipeline-name "${CODEPIPELINE_NAME}" \
      --pipeline-execution-id "${PIPELINE_EXECUTION_ID}"
    ```

## Acceptance checks

1. Connection status is `AVAILABLE`.
2. Latest signed release commit SHA appears in pipeline execution history.
3. Source stage transitions to `Succeeded`.

## References

- CodeConnections CloudFormation resource:
  <https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-codeconnections-connection.html>
- CodeConnections get-connection API:
  <https://docs.aws.amazon.com/cli/latest/reference/codeconnections/get-connection.html>
- CodePipeline source action with CodeConnections:
  <https://docs.aws.amazon.com/codepipeline/latest/userguide/action-reference-CodestarConnectionSource.html>
