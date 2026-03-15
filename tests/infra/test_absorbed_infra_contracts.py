"""Infra contract tests for absorbed Nova templates.

These checks are deterministic and enforce policy/path invariants from
SPEC-0013/SPEC-0014.
"""

from __future__ import annotations

import re

import yaml

from .helpers import REPO_ROOT
from .helpers import read_repo_file as _read

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


class _CfnYamlLoader(yaml.SafeLoader):
    """YAML loader that treats CloudFormation intrinsics as plain data."""


def _construct_cfn_tag(
    loader: _CfnYamlLoader,
    _tag_suffix: str,
    node: yaml.Node,
) -> object:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    raise TypeError(f"Unsupported YAML node: {type(node)!r}")


_CfnYamlLoader.add_multi_constructor("!", _construct_cfn_tag)


def _section(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    assert start != -1, f"Missing section marker: {start_marker}"
    end = text.find(end_marker, start)
    assert end != -1, f"Missing section terminator: {end_marker}"
    return text[start:end]


def _default_number_from_block(block: str) -> int:
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("Default:"):
            return int(stripped.removeprefix("Default:").strip().strip('"'))
    raise AssertionError("Expected Default entry in parameter block")


def _yaml_template(rel_path: str) -> dict[str, object]:
    payload = yaml.load(
        _read(rel_path),
        Loader=_CfnYamlLoader,  # noqa: S506 - subclasses SafeLoader
    )
    assert isinstance(payload, dict)
    return payload


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
        "CodeArtifactInternalNpmScope:",
        "ConstraintDescription: Must be a valid lowercase npm scope without @.",
        "InternalNpmPackageGroup:",
        "AWS::CodeArtifact::PackageGroup",
        "Pattern: !Sub /npm/${CodeArtifactInternalNpmScope}/*",
        "RestrictionMode: BLOCK",
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
        "ConstraintDescription: Must be a valid CodeArtifact repository name.",
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
        "ReleaseBuildspecPath:",
        "ValidateBuildspecPath:",
        (
            "ConstraintDescription: Must be a relative path without parent "
            "traversal."
        ),
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
    """Verify service base URL SSM template enforces canonical path and URL
    hygiene."""
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
    cfn_passrole_pattern = re.compile(
        r"Action:\n"
        r"\s+- iam:PassRole\n"
        r"\s*Resource:\n"
        r"\s+- !GetAtt CloudFormationExecutionRoleDev\.Arn\n"
        r"\s+- !GetAtt CloudFormationExecutionRoleProd\.Arn\n"
        r"\s*Condition:\n"
        r"\s*StringEquals:\n"
        r"\s*iam:PassedToService:\n"
        r"\s+- cloudformation\.amazonaws\.com",
        flags=re.MULTILINE,
    )
    assert cfn_passrole_pattern.search(text), (
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
    github_role_arn_pattern = (
        "arn:${AWS::Partition}:codepipeline:${AWS::Region}"
        ":${AWS::AccountId}:${Project}-${Application}-*"
    )
    assert github_role_arn_pattern in github_role_text
    assert "${FoundationStackName}-CodeArtifactDomainName" in github_role_text
    assert (
        "${FoundationStackName}-CodeArtifactRepositoryName" in github_role_text
    )
    assert "CodeArtifactPromotionSourceRepositoryName" in github_role_text
    assert "CodeArtifactPromotionDestinationRepositoryName" in github_role_text
    repo_dest_pattern = (
        "repository/${ResolvedCodeArtifactDomainName}/"
        "${PromotionDestinationRepositoryName}"
    )
    repo_src_pattern = (
        "repository/${ResolvedCodeArtifactDomainName}/"
        "${PromotionSourceRepositoryName}"
    )
    assert repo_dest_pattern in github_role_text
    assert repo_src_pattern in github_role_text
    assert "${CodeArtifactInternalNpmScope}" in github_role_text
    assert (
        "package/${ResolvedCodeArtifactDomainName}/"
        "${ResolvedCodeArtifactRepositoryName}/npm/" in github_role_text
    )
    assert (
        "package/${ResolvedCodeArtifactDomainName}/"
        "${PromotionSourceRepositoryName}/npm/" in github_role_text
    )
    assert (
        "package/${ResolvedCodeArtifactDomainName}/"
        "${PromotionDestinationRepositoryName}/npm/" in github_role_text
    )
    assert "sts:AWSServiceName: codeartifact.amazonaws.com" in github_role_text
    assert "codeartifact:CreatePackageGroup" in text
    assert "codeartifact:DescribePackageGroup" in text
    assert "codeartifact:UpdatePackageGroup" in text
    assert "codeartifact:UpdatePackageGroupOriginConfiguration" in text
    assert "package-group/${ResolvedCodeArtifactDomainName}/*" in text

    assert "ReleaseValidationTrustedPrincipalArn:" in text
    assert "release-validation-read" in text
    assert "BatchB" not in text

    validation_policy_block = re.search(
        r"(?ms)^  ReleaseValidationReadManagedPolicy:\n.*?(?=^Outputs:)",
        text,
    )
    assert validation_policy_block, (
        "Missing ReleaseValidationReadManagedPolicy block"
    )
    validation_policy_text = validation_policy_block.group(0)

    for required_action in [
        "codestar-connections:GetConnection",
        "codeconnections:GetConnection",
        "codeartifact:GetRepositoryEndpoint",
        "codeartifact:ReadFromRepository",
        "codepipeline:ListPipelines",
        "codepipeline:ListPipelineExecutions",
        "wafv2:GetWebACLForResource",
        "iam:GetRole",
    ]:
        assert required_action in validation_policy_text


def test_runtime_env_and_parameter_contracts() -> None:
    """Runtime templates must preserve env/parameter guardrails."""
    async_text = _read("infra/runtime/file_transfer/async.yml")
    ecr_text = _read("infra/runtime/ecr.yml")
    s3_text = _read("infra/runtime/file_transfer/s3.yml")
    worker_text = _read("infra/runtime/file_transfer/worker.yml")
    worker_template = _yaml_template("infra/runtime/file_transfer/worker.yml")
    service_text = _read("infra/runtime/ecs/service.yml")
    service_template = _yaml_template("infra/runtime/ecs/service.yml")

    assert "JobsVisibilityTimeoutSeconds" in async_text
    assert "MinValue: 30" in async_text
    assert "JobsMessageRetentionSeconds" in async_text
    assert "MaxValue: 1209599" in async_text
    assert "SqsManagedSseEnabled: true" in async_text
    assert "PointInTimeRecoveryEnabled: true" in async_text
    assert "GlobalSecondaryIndexes:" in async_text
    assert "IndexName: scope_id-created_at-index" in async_text
    assert "AttributeName: scope_id" in async_text
    assert "AttributeName: created_at" in async_text

    resources = worker_template["Resources"]
    assert isinstance(resources, dict)
    worker_task_definition = resources["WorkerTaskDefinition"]
    assert isinstance(worker_task_definition, dict)
    properties = worker_task_definition["Properties"]
    assert isinstance(properties, dict)
    container_definitions = properties["ContainerDefinitions"]
    assert isinstance(container_definitions, list)
    container = container_definitions[0]
    assert isinstance(container, dict)

    assert container["Command"] == ["nova-file-worker"]
    environment = container["Environment"]
    assert isinstance(environment, list)
    env_names = {
        entry["Name"]
        for entry in environment
        if isinstance(entry, dict) and isinstance(entry.get("Name"), str)
    }
    assert {
        "JOBS_ENABLED",
        "JOBS_RUNTIME_MODE",
        "JOBS_QUEUE_BACKEND",
        "JOBS_SQS_QUEUE_URL",
        "JOBS_API_BASE_URL",
        "FILE_TRANSFER_BUCKET",
        "FILE_TRANSFER_UPLOAD_PREFIX",
        "FILE_TRANSFER_EXPORT_PREFIX",
        "FILE_TRANSFER_TMP_PREFIX",
    }.issubset(env_names)
    assert {
        "FILE_TRANSFER_API_BASE_URL",
        "FILE_TRANSFER_JOBS_QUEUE_URL",
        "FILE_TRANSFER_JOBS_REGION",
        "APP_SYNC_PROCESSING_MAX_BYTES",
    }.isdisjoint(env_names)

    secrets = container["Secrets"]
    assert isinstance(secrets, list)
    secret_names = {
        entry["Name"]
        for entry in secrets
        if isinstance(entry, dict) and isinstance(entry.get("Name"), str)
    }
    assert secret_names == {"JOBS_WORKER_UPDATE_TOKEN"}
    parameters = worker_template["Parameters"]
    assert isinstance(parameters, dict)
    assert "JobsWorkerUpdateTokenSecretArn" in parameters
    assert "WorkerCommand" not in parameters
    assert "SyncProcessingMaxBytes" not in parameters

    service_resources = service_template["Resources"]
    assert isinstance(service_resources, dict)
    service_task_definition = service_resources["TaskDefinition"]
    assert isinstance(service_task_definition, dict)
    service_properties = service_task_definition["Properties"]
    assert isinstance(service_properties, dict)
    service_containers = service_properties["ContainerDefinitions"]
    assert isinstance(service_containers, list)
    service_container = service_containers[0]
    assert isinstance(service_container, dict)

    service_environment = service_container["Environment"]
    assert isinstance(service_environment, list)
    service_env_names = {
        entry["Name"]
        for entry in service_environment
        if isinstance(entry, dict) and isinstance(entry.get("Name"), str)
    }
    assert {
        "ENVIRONMENT",
        "AUTH_MODE",
        "FILE_TRANSFER_ENABLED",
        "JOBS_ENABLED",
        "JOBS_QUEUE_BACKEND",
        "JOBS_REPOSITORY_BACKEND",
        "JOBS_RUNTIME_MODE",
        "ACTIVITY_STORE_BACKEND",
    }.issubset(service_env_names)
    assert {
        "ENV",
        "ENV_DICT",
        "AUTH_APP_SECRET",
    }.isdisjoint(service_env_names)

    service_secrets = service_container["Secrets"]
    assert isinstance(service_secrets, list)
    service_secret_names = {
        entry["Name"]
        for entry in service_secrets
        if isinstance(entry, dict) and isinstance(entry.get("Name"), str)
    }
    assert "CACHE_REDIS_URL" not in service_secret_names
    assert "Name: CACHE_REDIS_URL" in service_text

    service_parameters = service_template["Parameters"]
    assert isinstance(service_parameters, dict)
    assert "EnvVars" not in service_parameters
    assert "UseLegacyEnvDict" not in service_parameters
    assert "JobsQueueUrl" in service_parameters
    assert "JobsTableName" in service_parameters
    assert "ActivityTableName" in service_parameters
    assert "CacheRedisUrlSecretArn" in service_parameters

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

    image_digest_wiring_pattern = (
        r"(?ms)^\s*Image:\s*!Sub(?:\s+|\n\s+).*?@\$\{ImageDigest\}"
    )
    assert re.search(image_digest_wiring_pattern, worker_text) is not None
    assert "DockerImageTag:" not in worker_text
    assert re.search(image_digest_wiring_pattern, service_text) is not None
    assert "DockerImageTag:" not in service_text

    assert "FileTransferAsyncParamsProvided:" in service_text
    assert "FileTransferAsyncRuntimeParamsProvided:" in service_text
    assert "FileTransferCacheParamsProvided:" in service_text
    assert "FileTransferCacheSecretProvided:" in service_text
    assert (
        "FileTransferJobsQueueArn, FileTransferJobsTableArn, and"
        in service_text
    )
    assert "JobsQueueUrl, JobsTableName, and ActivityTableName" in service_text
    assert "CacheRedisUrlSecretArn is required" in service_text
    assert (
        "FileTransferCacheSecurityGroupExportName is required" in service_text
    )
    assert "AllowExecutionRoleSecretsWildcard" not in ecr_text
    assert (
        "TaskExecutionSecretArns/TaskExecutionSsmParameterArns" not in ecr_text
    )
    assert "Prefix: !Ref TmpPrefix" in s3_text


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

    min_block = _section(
        worker_text,
        "  WorkerMinTaskCount:\n",
        "  WorkerMaxTaskCount:\n",
    )
    max_block = _section(
        worker_text,
        "  WorkerMaxTaskCount:\n",
        "  WorkerScaleOutQueueDepthTarget:\n",
    )
    min_count = _default_number_from_block(min_block)
    max_count = _default_number_from_block(max_block)
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


def test_ecs_native_blue_green_authority_contracts() -> None:
    """Batch B1 contract: ECS template codifies ECS-native blue/green."""
    text = _read("infra/runtime/ecs/service.yml")

    required_tokens = [
        "EcsInfrastructureRoleArn:",
        "BlueGreenTrafficControlParamsProvided:",
        "DeploymentController:",
        "Type: ECS",
        "Strategy: BLUE_GREEN",
        "BakeTimeInMinutes: !Ref BlueGreenBakeTimeInMinutes",
        "LoadBalancerTargetGroupBlue:",
        "LoadBalancerTargetGroupGreen:",
        "AdvancedConfiguration:",
        "AlternateTargetGroupArn: !Ref LoadBalancerTargetGroupGreen",
        "ProductionListenerRule: !Ref ListenerRule",
        "RoleArn: !Ref EcsInfrastructureRoleArn",
        "HasTestTrafficListenerArn:",
        "Condition: HasTestTrafficListenerArn",
        "TestListenerRule: !If",
        "AlarmNames:",
        "Rollback: true",
        "ReadinessHealthCheckPath:",
        "HealthCheckPath: !Ref ReadinessHealthCheckPath",
        "ForwardConfig:",
        "Weight: 1",
        "Weight: 0",
    ]
    for token in required_tokens:
        assert token in text, f"Missing blue/green contract token: {token}"

    assert "AWS::CodeDeploy::Application" not in text
    assert "AWS::CodeDeploy::DeploymentGroup" not in text
    assert "CodeDeploy" not in text


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
        "BlueGreenBakeTimeInMinutes:",
        "BlueTargetGroupArn:",
        "BlueTargetGroupName:",
        "GreenTargetGroupArn:",
        "GreenTargetGroupName:",
        "ImageUri",
        "LoadBalancerTargetGroupGreen.TargetGroupFullName",
    ]:
        assert token in text


def test_cluster_tls_and_blue_green_test_listener_contracts() -> None:
    """Cluster template must expose TLS policy + optional test listener."""
    text = _read("infra/runtime/ecs/cluster.yml")

    for token in [
        "TlsSecurityPolicy:",
        "EnableBlueGreenTestListener:",
        "BlueGreenTestListenerPort:",
        "BlueGreenTestListenerPortNotReserved:",
        "CreateBlueGreenTestListener:",
        "ALBListenerForwardHTTPSTest:",
        "Condition: CreateBlueGreenTestListener",
        "Port: !Ref BlueGreenTestListenerPort",
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
        "BlueGreenTestListenerPort must not be 80 or 443",
        "SourcePrefixListId: !Ref AlbIngressPrefixListId",
        "CidrIp: !Ref AlbIngressCidr",
        "SourceSecurityGroupId: !Ref AlbIngressSourceSecurityGroupId",
    ]:
        assert token in text

    assert "PrefixListMap:" not in text
    assert "3MInternal" not in text
    assert "CodeDeploy" not in text


def test_release_buildspec_dual_digest_contracts() -> None:
    """Release buildspec must publish both workload images and digests."""
    text = _read("buildspecs/buildspec-release.yml")

    for token in [
        "FILE_IMAGE_DIGEST",
        "AUTH_IMAGE_DIGEST",
        "FILE_DOCKERFILE_PATH",
        "AUTH_DOCKERFILE_PATH",
        'FILE_IMAGE_TAG="file-${IMAGE_TAG}"',
        'AUTH_IMAGE_TAG="auth-${IMAGE_TAG}"',
        "docker build \\",
        'docker push "${ECR_REPOSITORY_URI}:${FILE_IMAGE_TAG}"',
        'docker push "${ECR_REPOSITORY_URI}:${AUTH_IMAGE_TAG}"',
        'FILE_IMAGE_DIGEST="${FILE_DIGEST}"',
        'AUTH_IMAGE_DIGEST="${AUTH_DIGEST}"',
    ]:
        assert token in text

    assert "\n    - IMAGE_DIGEST\n" not in text


def test_pipeline_dual_digest_promotion_contract() -> None:
    """Pipeline must support selecting the promoted workload digest variable."""
    text = _read("infra/nova/nova-ci-cd.yml")

    for token in [
        "DeployImageDigestVariable:",
        "FILE_IMAGE_DIGEST",
        "AUTH_IMAGE_DIGEST",
        "UseAuthImageDigestVariable:",
        "#{ReleaseBuild.FILE_IMAGE_DIGEST}",
        "#{ReleaseBuild.AUTH_IMAGE_DIGEST}",
    ]:
        assert token in text


def test_reusable_runtime_workflow_digest_contract() -> None:
    """Reusable runtime workflow must accept image digests, not image tags."""
    text = _read(".github/workflows/reusable-deploy-runtime.yml")

    for token in [
        "image_digest:",
        "IMAGE_DIGEST:",
        'payload["ImageDigest"] = image_digest',
    ]:
        assert token in text

    assert "image_tag:" not in text
    assert 'payload["DockerImageTag"]' not in text


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


def test_nova_iam_validation_read_contracts() -> None:
    """IAM template must expose release-validation read access contracts."""
    text = _read("infra/nova/nova-iam-roles.yml")

    for token in [
        "ReleaseValidationReadRole:",
        "ReleaseValidationReadManagedPolicy:",
        "codepipeline:ListActionExecutions",
        "codepipeline:GetPipeline",
        "cloudformation:DescribeStacks",
        "ecs:DescribeClusters",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeRules",
        "wafv2:GetWebACLForResource",
        "iam:GetRole",
    ]:
        assert token in text
