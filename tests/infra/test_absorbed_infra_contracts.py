"""Infra contract tests for absorbed Nova templates.

These checks are deterministic and enforce policy/path invariants from
SPEC-0013/SPEC-0014.
"""

from __future__ import annotations

import re

from .helpers import REPO_ROOT, _read
RUNTIME_DEPLOYABLE_TEMPLATES = (
    "infra/runtime/ecr.yml",
    "infra/runtime/ecs/cluster.yml",
    "infra/runtime/ecs/service.yml",
    "infra/runtime/file_transfer/async.yml",
    "infra/runtime/file_transfer/cache.yml",
    "infra/runtime/file_transfer/s3.yml",
    "infra/runtime/file_transfer/worker.yml",
    "infra/runtime/kms.yml",
    "infra/runtime/observability/ecs-observability-baseline.yml",
)


def test_absorbed_template_paths_present() -> None:
    """Absorbed infra templates must exist under Nova-owned paths."""
    required_templates = [
        "infra/nova/nova-foundation.yml",
        "infra/nova/nova-ci-cd.yml",
        "infra/nova/nova-codebuild-release.yml",
        "infra/nova/nova-iam-roles.yml",
        "infra/nova/deploy/image-digest-ssm.yml",
        "infra/nova/deploy/service-base-url-ssm.yml",
        *RUNTIME_DEPLOYABLE_TEMPLATES,
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
    assert "DevServiceBaseUrl:" in text
    assert "ProdServiceBaseUrl:" in text
    assert "AllowedPattern:" in text and "httpbin" in text

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

    assert (
        re.search(
            r"(?ms)-\s*!If\s*\n\s*-\s*HasApprovalTopic\s*\n\s*-\s*Name:\s*ManualApproval",
            text,
        )
        is None
    ), "ManualApproval stage must be unconditional in pipeline stages."
    assert "ApproveProdPromotion" in text
    assert "Provider: Manual" in text


def test_foundation_exports_and_stack_wiring_contracts() -> None:
    """Foundation + stack wiring contracts must stay consistent."""
    foundation_text = _read("infra/nova/nova-foundation.yml")
    iam_text = _read("infra/nova/nova-iam-roles.yml")
    codebuild_text = _read("infra/nova/nova-codebuild-release.yml")
    pipeline_text = _read("infra/nova/nova-ci-cd.yml")

    for token in [
        "ArtifactBucket:",
        "CreateArtifactBucket:",
        "CodeConnection:",
        "CreateConnection:",
        "ManualApprovalTopic:",
        "CreateManualApprovalTopic:",
        "ManualApprovalTopicArn:",
        "${AWS::StackName}-ArtifactBucketName",
        "${AWS::StackName}-CodeArtifactDomainName",
        "${AWS::StackName}-CodeArtifactRepositoryName",
        "${AWS::StackName}-EcrRepositoryArn",
        "${AWS::StackName}-EcrRepositoryName",
        "${AWS::StackName}-EcrRepositoryUri",
        "${AWS::StackName}-ConnectionName",
        "${AWS::StackName}-ConnectionArn",
        "${AWS::StackName}-ManualApprovalTopicArn",
    ]:
        assert token in foundation_text

    for token in [
        "FoundationStackName:",
        "${FoundationStackName}-ArtifactBucketName",
        "${FoundationStackName}-CodeArtifactDomainName",
        "${FoundationStackName}-CodeArtifactRepositoryName",
        "CodeArtifactPromotionSourceRepositoryName:",
        "CodeArtifactPromotionDestinationRepositoryName:",
        "RequireDistinctCodeArtifactPromotionRepositories:",
        "${FoundationStackName}-EcrRepositoryArn",
        "${FoundationStackName}-ManualApprovalTopicArn",
        "${AWS::StackName}-CodePipelineServiceRoleArn",
        "${AWS::StackName}-CodeBuildReleaseRoleArn",
        "${AWS::StackName}-CloudFormationExecutionRoleDevArn",
        "${AWS::StackName}-CloudFormationExecutionRoleProdArn",
    ]:
        assert token in iam_text

    for token in [
        "FoundationStackName:",
        "IamRolesStackName:",
        "${FoundationStackName}-CodeArtifactDomainName",
        "${FoundationStackName}-CodeArtifactRepositoryName",
        "${FoundationStackName}-EcrRepositoryUri",
        "${FoundationStackName}-EcrRepositoryName",
        "${IamRolesStackName}-CodeBuildReleaseRoleArn",
        "${AWS::StackName}-ReleaseBuildProjectName",
        "${AWS::StackName}-DeployValidateProjectName",
    ]:
        assert token in codebuild_text

    for token in [
        "FoundationStackName:",
        "IamRolesStackName:",
        "CodeBuildStackName:",
        "${FoundationStackName}-ArtifactBucketName",
        "${FoundationStackName}-ConnectionArn",
        "${FoundationStackName}-ManualApprovalTopicArn",
        "${CodeBuildStackName}-ReleaseBuildProjectName",
        "${CodeBuildStackName}-DeployValidateProjectName",
        "${IamRolesStackName}-CodePipelineServiceRoleArn",
        "${IamRolesStackName}-CloudFormationExecutionRoleDevArn",
        "${IamRolesStackName}-CloudFormationExecutionRoleProdArn",
    ]:
        assert token in pipeline_text


def test_digest_marker_path_and_env_contracts() -> None:
    """Digest marker path and constraints must stay stable."""
    text = _read("infra/nova/deploy/image-digest-ssm.yml")

    assert (
        'Name: !Sub "/nova/${Environment}/${ServiceName}/image-digest"' in text
    )
    assert "AllowedValues:" in text and "- dev" in text and "- prod" in text
    assert 'AllowedPattern: "^sha256:[A-Fa-f0-9]{64}$"' in text


def test_service_base_url_ssm_path_and_url_constraints() -> None:
    """Verify service base URL SSM template enforces canonical path and URL hygiene."""
    text = _read("infra/nova/deploy/service-base-url-ssm.yml")

    assert 'Name: !Sub "/nova/${Environment}/${ServiceName}/base-url"' in text
    assert "AllowedValues:" in text and "- dev" in text and "- prod" in text
    assert "AllowedPattern:" in text
    assert "httpbin" in text
    assert "placeholder" in text
    assert "example\\.com" in text


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
    assert "cloudformation.amazonaws.com" in text
    cfn_passrole_block = (
        "Action:\n"
        "                  - iam:PassRole\n"
        "                Resource:\n"
        "                  - !GetAtt CloudFormationExecutionRoleDev.Arn\n"
        "                  - !GetAtt CloudFormationExecutionRoleProd.Arn\n"
        "                Condition:\n"
        "                  StringEquals:\n"
        "                    iam:PassedToService:\n"
        "                      - cloudformation.amazonaws.com"
    )
    assert cfn_passrole_block in text, (
        "CodePipeline iam:PassRole must require "
        "iam:PassedToService=cloudformation.amazonaws.com"
    )

    github_role_start = text.find("  GitHubOIDCReleaseRole:")
    codepipeline_role_start = text.find("  CodePipelineServiceRole:")
    assert github_role_start != -1, "Missing GitHubOIDCReleaseRole block"
    assert codepipeline_role_start != -1, (
        "Missing CodePipelineServiceRole block"
    )
    github_role_text = text[github_role_start:codepipeline_role_start]
    for required_action in [
        "codepipeline:StartPipelineExecution",
        "codepipeline:GetPipelineState",
        "codepipeline:ListPipelineExecutions",
        "codepipeline:GetPipelineExecution",
        "codepipeline:PutApprovalResult",
        "codeartifact:GetAuthorizationToken",
        "codeartifact:GetRepositoryEndpoint",
        "codeartifact:PublishPackageVersion",
        "codeartifact:PutPackageMetadata",
        "codeartifact:DescribePackageVersion",
        "codeartifact:ReadFromRepository",
        "codeartifact:CopyPackageVersions",
        "sts:GetServiceBearerToken",
    ]:
        assert required_action in github_role_text
    assert (
        "arn:${AWS::Partition}:codepipeline:${AWS::Region}:${AWS::AccountId}:${Project}-${Application}-*"
        in github_role_text
    )
    assert "${FoundationStackName}-CodeArtifactDomainName" in github_role_text
    assert (
        "${FoundationStackName}-CodeArtifactRepositoryName" in github_role_text
    )
    assert "CodeArtifactPromotionSourceRepositoryName" in github_role_text
    assert "CodeArtifactPromotionDestinationRepositoryName" in github_role_text
    assert (
        "repository/${ResolvedCodeArtifactDomainName}/${PromotionDestinationRepositoryName}"
        in github_role_text
    )
    assert (
        "repository/${ResolvedCodeArtifactDomainName}/${PromotionSourceRepositoryName}"
        in github_role_text
    )
    assert "sts:AWSServiceName: codeartifact.amazonaws.com" in github_role_text

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


def test_pipeline_validation_base_url_parameters_are_constrained() -> None:
    """Pipeline template must constrain deploy validation base URL inputs."""
    text = _read("infra/nova/nova-ci-cd.yml")
    required_constraint_description = (
        "ConstraintDescription: Must be an HTTPS URL and not a "
        "placeholder/test host."
    )
    required_allowed_pattern = 'AllowedPattern: "^https://'

    for parameter_name in ["DevServiceBaseUrl", "ProdServiceBaseUrl"]:
        parameter_block_pattern = (
            rf"(?ms)^  {re.escape(parameter_name)}:\n"
            r"(?:    .*\n)*?(?=^  \S|\Z)"
        )
        match = re.search(
            parameter_block_pattern,
            text,
        )
        assert match is not None, f"missing {parameter_name} block in template"
        block = match.group(0)
        assert required_allowed_pattern in block, (
            f"missing HTTPS constraint for {parameter_name} block"
        )
        assert required_constraint_description in block, (
            f"missing constraint description for {parameter_name} block"
        )


def test_runtime_templates_do_not_contain_jinja_markers() -> None:
    """Deployable runtime templates must be native CFN (no Jinja tokens)."""
    jinja_marker_pattern = re.compile(r"\{\%|\%\}|\{\#|\#\}|\{\{(?!resolve:)")
    violations: list[str] = []

    for rel_path in RUNTIME_DEPLOYABLE_TEMPLATES:
        text = _read(rel_path)
        for match in jinja_marker_pattern.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            violations.append(f"{rel_path}:{line_number}: {match.group(0)!r}")

    assert not violations, (
        "Found Jinja markers in deployable runtime templates:\n"
        + "\n".join(violations)
    )


def test_cache_template_uses_native_dynamic_reference_syntax() -> None:
    """Cache template must keep native CFN dynamic references."""
    cache_text = _read("infra/runtime/file_transfer/cache.yml")

    assert (
        "{{resolve:secretsmanager:${FileTransferCacheAuthTokenSecret}:SecretString}}"
        in cache_text
    )
    assert "{{ '{{' }}" not in cache_text
    assert "{{ '}}' }}" not in cache_text


def test_ecs_service_desired_count_and_profile_wiring_contract() -> None:
    """ECS service template must expose desired-count/profile wiring."""
    service_text = _read("infra/runtime/ecs/service.yml")

    assert (
        re.search(
            r"DesiredCount:\n\s+Type:\s+Number\n\s+Default:\s+1",
            service_text,
        )
        is not None
    )
    assert "RuntimeProfile:" in service_text
    assert "DesiredCount: !Ref DesiredCount" in service_text
    assert "- Name: NOVA_RUNTIME_PROFILE" in service_text
    assert "Key: RuntimeProfile" in service_text


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
        "AlbIngressPrefixListId:",
        "AlbIngressCidr:",
        "AlbIngressSourceSecurityGroupId:",
        "RequireExactlyOneAlbIngressSource:",
        "HasAlbIngressPrefixListId:",
        "HasAlbIngressCidr:",
        "HasAlbIngressSourceSecurityGroupId:",
        "SourcePrefixListId: !Ref AlbIngressPrefixListId",
        "CidrIp: !Ref AlbIngressCidr",
        "SourceSecurityGroupId: !Ref AlbIngressSourceSecurityGroupId",
    ]:
        assert token in text

    assert "PrefixListMap:" not in text
    assert "3MInternal" not in text


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

    for stage_name in ["ValidateDev", "ValidateProd"]:
        stage_match = re.search(
            rf"(?ms)^\s*-\s+Name:\s+{stage_name}\s*$"
            rf"(?P<body>.*?)(?=^        - Name:\s+[A-Za-z0-9_]+|\Z)",
            text,
        )
        assert stage_match is not None, f"Missing {stage_name} stage"
        stage_body = stage_match.group("body")
        assert "InputArtifacts:" in stage_body
        assert "- Name: AppSourceOutput" in stage_body
        assert "BuildOutput" not in stage_body


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
