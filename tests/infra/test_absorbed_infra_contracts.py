"""Infra contract tests for absorbed Nova templates.

These checks are deterministic and enforce policy/path invariants from
SPEC-0013/SPEC-0014.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Expected template file to exist: {path}"
    return path.read_text(encoding="utf-8")


def test_absorbed_template_paths_present() -> None:
    """Absorbed infra templates must exist under Nova-owned paths."""
    required_templates = [
        "infra/nova/nova-ci-cd.yml",
        "infra/nova/nova-codebuild-release.yml",
        "infra/nova/nova-iam-roles.yml",
        "infra/nova/deploy/image-digest-ssm.yml",
        "infra/runtime/ecr.yml",
        "infra/runtime/ecs/cluster.yml",
        "infra/runtime/ecs/service.yml",
        "infra/runtime/file_transfer/async.yml",
        "infra/runtime/file_transfer/cache.yml",
        "infra/runtime/file_transfer/s3.yml",
        "infra/runtime/file_transfer/worker.yml",
        "infra/runtime/kms.yml",
        "infra/runtime/observability/ecs-observability-baseline.yml",
    ]

    missing = [
        path for path in required_templates if not (REPO_ROOT / path).is_file()
    ]
    assert not missing, f"Missing absorbed templates: {missing}"


def test_pipeline_single_source_contract() -> None:
    """Pipeline must use AppSourceOutput only."""
    text = _read("infra/nova/nova-ci-cd.yml")

    assert "InfraSourceOutput" not in text
    assert (
        "TemplatePath: AppSourceOutput::infra/nova/deploy/image-digest-ssm.yml"
        in text
    )

    expected_stage_order = [
        "Source",
        "Build",
        "DeployDev",
        "ValidateDev",
        "ManualApproval",
        "DeployProd",
        "ValidateProd",
    ]
    stage_name_pattern = re.compile(
        r"^\s*-\s+Name:\s*(?P<name>[A-Za-z0-9_]+)\s*$",
        flags=re.MULTILINE,
    )
    stage_names = [
        match.group("name") for match in stage_name_pattern.finditer(text)
    ]
    assert all(name in stage_names for name in expected_stage_order), (
        "Missing expected pipeline stage(s)"
    )
    indices = [stage_names.index(name) for name in expected_stage_order]
    assert indices == sorted(indices), "Pipeline stage order contract drifted"


def test_digest_marker_path_and_env_contracts() -> None:
    """Digest marker path and constraints must stay stable."""
    text = _read("infra/nova/deploy/image-digest-ssm.yml")

    assert (
        'Name: !Sub "/nova/${Environment}/${ServiceName}/image-digest"' in text
    )
    assert "AllowedValues:" in text and "- dev" in text and "- prod" in text
    assert 'AllowedPattern: "^sha256:[A-Fa-f0-9]{64}$"' in text


def test_iam_scope_constraints_for_release_roles() -> None:
    """Critical IAM constraints must remain tightly scoped."""
    text = _read("infra/nova/nova-iam-roles.yml")

    assert "token.actions.githubusercontent.com:aud: sts.amazonaws.com" in text
    assert (
        "repo:${RepositoryOwner}/${RepositoryName}:ref:refs/heads/${MainBranchName}"
        in text
    )

    passrole_blocks = re.findall(
        r"Action:\n"
        r"\s*- iam:PassRole\n"
        r"\s*Resource:(?P<resources>(?:\n\s*- .*?)+)\n"
        r"\s*Condition:\n"
        r"\s*StringEquals:\n"
        r"\s*iam:PassedToService:\n"
        r"\s*- ecs-tasks\.amazonaws\.com",
        text,
        flags=re.MULTILINE,
    )
    assert passrole_blocks, "Expected iam:PassRole policy blocks"
    wildcard_resource_pattern = re.compile(r"^\s*-\s*(?:\*|['\"]\*['\"])\s*$")
    allowed_passrole_resource_pattern = re.compile(
        r'^-\s+!Sub\s+"arn:\$\{AWS::Partition\}:iam::\$\{AWS::AccountId\}:role/\$\{Project\}-\$\{Application\}-\*-ecs-task(?:-execution)?-\$\{AWS::Region\}"$'
    )
    for block in passrole_blocks:
        resource_lines = [line.strip() for line in block.splitlines()]
        assert not any(
            wildcard_resource_pattern.match(line) for line in resource_lines
        ), "iam:PassRole must not allow wildcard-only resources"
        resource_lines = [
            line for line in resource_lines if line.startswith("- !Sub ")
        ]
        assert resource_lines, (
            "iam:PassRole block missing explicit resource ARNs"
        )
        assert all(
            allowed_passrole_resource_pattern.match(line)
            for line in resource_lines
        ), (
            "iam:PassRole resources must be scoped to ECS "
            "task and execution roles"
        )

    assert "iam:PassedToService:" in text
    assert "ecs-tasks.amazonaws.com" in text
    assert "BatchBOperatorPrincipalArn:" in text
    assert "batch-b-validation-read" in text

    batch_b_role_block = re.search(
        r"(?ms)^  BatchBValidationOperatorRole:\n(?:^    .*\n)+",
        text,
    )
    assert batch_b_role_block, "Missing BatchBValidationOperatorRole block"
    batch_b_text = batch_b_role_block.group(0)

    for required_action in [
        "codeconnections:GetConnection",
        "codepipeline:ListPipelines",
        "codepipeline:ListPipelineExecutions",
        "codedeploy:ListApplications",
    ]:
        assert required_action in batch_b_text


def test_runtime_env_and_parameter_contracts() -> None:
    """Runtime templates must preserve env/parameter guardrails."""
    async_text = _read("infra/runtime/file_transfer/async.yml")
    worker_text = _read("infra/runtime/file_transfer/worker.yml")
    service_text = _read("infra/runtime/ecs/service.yml")

    assert "JobsVisibilityTimeoutSeconds" in async_text
    assert "MinValue: 30" in async_text
    assert "JobsMessageRetentionSeconds" in async_text
    assert "MaxValue: 1209599" in async_text
    assert "SqsManagedSseEnabled: true" in async_text
    assert "PointInTimeRecoveryEnabled: true" in async_text

    for env_name in [
        "FILE_TRANSFER_JOBS_QUEUE_URL",
        "FILE_TRANSFER_JOBS_REGION",
        "FILE_TRANSFER_BUCKET",
        "FILE_TRANSFER_UPLOAD_PREFIX",
        "FILE_TRANSFER_EXPORT_PREFIX",
        "FILE_TRANSFER_TMP_PREFIX",
        "APP_SYNC_PROCESSING_MAX_BYTES",
    ]:
        assert f"- Name: {env_name}" in worker_text

    for required in [
        "JobsDeadLetterQueue:",
        "RedrivePolicy:",
        "deadLetterTargetArn: !GetAtt JobsDeadLetterQueue.Arn",
        "maxReceiveCount: !Ref JobsMaxReceiveCount",
        "WorkerScalableTarget:",
        "AWS::ApplicationAutoScaling::ScalableTarget",
        "WorkerQueueDepthTargetTrackingPolicy:",
        "MetricName: ApproximateNumberOfMessagesVisible",
        "WorkerQueueAgeTargetTrackingPolicy:",
        "MetricName: ApproximateAgeOfOldestMessage",
        'ResourceId: !Sub "service/${EcsClusterName}/'
        '${Project}-${Application}-${WorkerServiceName}"',
    ]:
        assert required in worker_text or required in async_text

    assert "FileTransferAsyncParamsProvided:" in service_text
    assert "FileTransferCacheParamsProvided:" in service_text
    assert (
        "FileTransferJobsQueueArn, FileTransferJobsTableArn, and"
        in service_text
    )
    assert (
        "FileTransferCacheSecurityGroupExportName is required" in service_text
    )


def test_worker_autoscaling_parameter_bounds_contract() -> None:
    """Worker autoscaling defaults must preserve min <= max."""
    worker_text = _read("infra/runtime/file_transfer/worker.yml")

    min_match = re.search(
        r"WorkerMinTaskCount:\n(?:\s+.+\n)*?\s+Default:\s+(?P<value>\d+)",
        worker_text,
    )
    max_match = re.search(
        r"WorkerMaxTaskCount:\n(?:\s+.+\n)*?\s+Default:\s+(?P<value>\d+)",
        worker_text,
    )

    assert min_match and max_match, (
        "Expected WorkerMinTaskCount/WorkerMaxTaskCount defaults "
        "in worker template"
    )

    min_count = int(min_match.group("value"))
    max_count = int(max_match.group("value"))
    assert min_count <= max_count, (
        "WorkerMinTaskCount must be less than or equal to WorkerMaxTaskCount"
    )


def test_observability_security_cost_baseline_contracts() -> None:
    """Batch A4 baseline template must enforce required hardening controls."""
    text = _read("infra/runtime/observability/ecs-observability-baseline.yml")

    for required in [
        "ApiLatencyP95RollbackAlarm",
        "Api5xxErrorRateRollbackAlarm",
        "ServiceLogRetentionPolicy",
        "ServiceObservabilityDashboard",
        "EcsScalableTarget",
        "MonthlyEstimatedChargesAlarm",
        "DeploymentRollbackAlarmNamesCsv",
    ]:
        assert required in text

    assert "RetentionInDays: !If [IsProd, 90, 30]" in text
    assert "Namespace: AWS/ECS" in text
    assert "Namespace: AWS/Billing" in text
    assert "AWS::ApplicationAutoScaling::ScalableTarget" in text
    assert "MinValue: 60" in text
    assert "Condition: IsUsEast1" in text
    assert "ManageLogGroupRetentionPolicy" in text
    assert "ServiceLogKmsKeyArn" in text
    assert "UseServiceLogCMK" in text
    assert "KmsKeyId: !If [UseServiceLogCMK" in text


def test_ecs_codedeploy_blue_green_authority_contracts() -> None:
    """Batch B1 contract: ECS template codifies CodeDeploy blue/green."""
    text = _read("infra/runtime/ecs/service.yml")

    required_tokens = [
        "EnableBlueGreenDeployAuthority:",
        "UseCodeDeployBlueGreen:",
        "CodeDeployBlueGreenParamsProvided:",
        "CodeDeployEcsApplication:",
        "Type: AWS::CodeDeploy::Application",
        "CodeDeployEcsDeploymentGroup:",
        "Type: AWS::CodeDeploy::DeploymentGroup",
        "ComputePlatform: ECS",
        "DeploymentController:",
        "Type: !If [UseCodeDeployBlueGreen, CODE_DEPLOY, ECS]",
        "LoadBalancerTargetGroupBlue:",
        "LoadBalancerTargetGroupGreen:",
        "TargetGroupPairInfoList:",
        "ProdTrafficRoute:",
        "TestTrafficRoute:",
        "BlueGreenDeploymentConfiguration:",
        "DeploymentReadyOption:",
        "ActionOnTimeout: !Ref BlueGreenReadinessActionOnTimeout",
        "AlarmConfiguration:",
        "AutoRollbackConfiguration:",
        "DEPLOYMENT_STOP_ON_ALARM",
        "DEPLOYMENT_STOP_ON_REQUEST",
        "ReadinessHealthCheckPath:",
        "HealthCheckPath: !Ref ReadinessHealthCheckPath",
    ]
    for token in required_tokens:
        assert token in text, f"Missing blue/green contract token: {token}"

    assert (
        "CodeDeployServiceRoleArn, TestTrafficListenerArn, and both rollback"
        in text
    )
    assert "at least one" not in text
    assert "Enabled: true" in text


def test_ecs_service_target_group_tuning_contracts() -> None:
    """Service template must expose target-group tuning controls."""
    text = _read("infra/runtime/ecs/service.yml")

    for token in [
        "TargetGroupHealthCheckTimeoutSeconds:",
        "TargetGroupHealthCheckIntervalSeconds:",
        "TargetGroupHealthyThresholdCount:",
        "TargetGroupUnhealthyThresholdCount:",
        "TargetGroupDeregistrationDelaySeconds:",
        "HealthCheckTimeoutSeconds: !Ref TargetGroupHealthCheckTimeoutSeconds",
        (
            "HealthCheckIntervalSeconds: !Ref "
            "TargetGroupHealthCheckIntervalSeconds"
        ),
        "HealthyThresholdCount: !Ref TargetGroupHealthyThresholdCount",
        "UnhealthyThresholdCount: !Ref TargetGroupUnhealthyThresholdCount",
        'Value: !Sub "${TargetGroupDeregistrationDelaySeconds}"',
        "BlueTargetGroupArn:",
        "BlueTargetGroupName:",
        "GreenTargetGroupArn:",
        "GreenTargetGroupName:",
        "ResolvedCodeDeployApplicationName:",
        "ResolvedCodeDeployDeploymentGroupName:",
    ]:
        assert token in text


def test_cluster_tls_and_codedeploy_test_listener_contracts() -> None:
    """Cluster template must expose TLS policy + optional test listener."""
    text = _read("infra/runtime/ecs/cluster.yml")

    for token in [
        "TlsSecurityPolicy:",
        "EnableCodeDeployTestListener:",
        "CodeDeployTestListenerPort:",
        "CreateCodeDeployTestListener:",
        "ALBListenerForwardHTTPSTest:",
        "Condition: CreateCodeDeployTestListener",
        "Port: !Ref CodeDeployTestListenerPort",
        "SslPolicy: !Ref TlsSecurityPolicy",
        "TestListenerArn:",
        ":testlistenerarn",
    ]:
        assert token in text


def test_nova_ci_cd_validation_env_contracts() -> None:
    """Validate stages must pass canonical + legacy validation vars."""
    text = _read("infra/nova/nova-ci-cd.yml")

    for token in [
        "ValidationCanonicalPaths:",
        "ValidationLegacy404Paths:",
        '"name":"VALIDATION_BASE_URL"',
        '"name":"SERVICE_BASE_URL"',
        '"name":"VALIDATION_CANONICAL_PATHS"',
        '"name":"VALIDATION_LEGACY_404_PATHS"',
    ]:
        assert token in text


def test_nova_iam_codedeploy_role_and_validation_read_contracts() -> None:
    """IAM template must expose CodeDeploy ECS role and expanded reads."""
    text = _read("infra/nova/nova-iam-roles.yml")

    for token in [
        "CodeDeployEcsServiceRole:",
        "AWSCodeDeployRoleForECS",
        "CodeDeployEcsServiceRoleArn:",
        "codepipeline:ListActionExecutions",
        "codepipeline:GetPipeline",
        "codedeploy:ListDeploymentGroups",
        "codedeploy:ListDeployments",
        "codedeploy:GetApplication",
        "cloudformation:DescribeStacks",
        "ecs:DescribeClusters",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeRules",
    ]:
        assert token in text
