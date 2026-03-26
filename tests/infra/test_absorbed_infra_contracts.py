"""Infra contract tests for absorbed Nova templates.

These checks are deterministic and enforce policy/path invariants from
SPEC-0013/SPEC-0014.
"""

from __future__ import annotations

import re

import yaml

from .helpers import (
    REPO_ROOT,
    load_repo_module,
    section_text,
)
from .helpers import (
    read_repo_file as _read,
)

runtime_config_contract = load_repo_module(
    "tests.infra.runtime_config_contract",
    "scripts/release/runtime_config_contract.py",
)
build_contract_payload = runtime_config_contract.build_contract_payload

RUNTIME_DEPLOYABLE_TEMPLATES = (
    "infra/runtime/ecr.yml",
    "infra/runtime/edge/cloudfront.yml",
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


yaml.add_multi_constructor(
    "!",
    _construct_cfn_tag,
    Loader=_CfnYamlLoader,
)


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


def _collect_named_entries(node: object) -> set[str]:
    names: set[str] = set()
    if isinstance(node, dict):
        name = node.get("Name")
        if isinstance(name, str):
            names.add(name)
        for value in node.values():
            names.update(_collect_named_entries(value))
    elif isinstance(node, list):
        for item in node:
            names.update(_collect_named_entries(item))
    return names


def _collect_env_values(node: object) -> dict[str, str]:
    values: dict[str, str] = {}
    if isinstance(node, list):
        for item in node:
            if not isinstance(item, dict):
                continue
            name = item.get("Name")
            value = item.get("Value")
            if isinstance(name, str) and isinstance(value, str):
                values[name] = value
    return values


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
        "InternalNpmPackageGroup:",
        "AWS::CodeArtifact::PackageGroup",
        "Pattern: /npm/nova/*",
        "RestrictionMode: BLOCK",
        "LifecycleConfiguration:",
        "ArtifactBucketLifecyclePolicy",
        'Prefix: ""',
        "AbortIncompleteMultipartUpload:",
        "NoncurrentVersionExpiration:",
        "ManualApprovalTopicArn:",
        "ShouldExportConnectionName:",
        "${AWS::StackName}-ArtifactBucketName",
        "${AWS::StackName}-CodeArtifactDomainName",
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
        "CodeArtifactStagingRepositoryName:",
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
        "CodeArtifactStagingRepositoryName:",
        "CODEARTIFACT_STAGING_REPOSITORY",
        "${FoundationStackName}-EcrRepositoryUri",
        "${FoundationStackName}-EcrRepositoryName",
        "${IamRolesStackName}-CodeBuildReleaseRoleArn",
        "CodeBuildLogRetentionInDays:",
        "CloudWatchLogs:",
        "RetentionInDays: !Ref CodeBuildLogRetentionInDays",
        "AllowedValues:",
        "  - 1",
        "  - 3",
        "  - 5",
        "  - 7",
        "  - 14",
        "  - 30",
        "  - 60",
        "  - 90",
        "  - 120",
        "  - 150",
        "  - 180",
        "  - 365",
        "  - 400",
        "  - 545",
        "  - 731",
        "  - 1096",
        "  - 1827",
        "  - 2192",
        "  - 2557",
        "  - 2922",
        "  - 3288",
        "  - 3653",
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
    assert "CodeArtifactStagingRepositoryName" in github_role_text
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
    assert "/npm/nova/*" in github_role_text
    assert "/generic/*" in github_role_text
    assert (
        "package/${ResolvedCodeArtifactDomainName}/"
        "${StagingRepositoryName}/npm/" in github_role_text
    )
    assert (
        "package/${ResolvedCodeArtifactDomainName}/"
        "${StagingRepositoryName}/generic/" in github_role_text
    )
    assert (
        "package/${ResolvedCodeArtifactDomainName}/"
        "${PromotionSourceRepositoryName}/generic/" in github_role_text
    )
    assert (
        "package/${ResolvedCodeArtifactDomainName}/"
        "${PromotionDestinationRepositoryName}/generic/" in github_role_text
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
    contract = build_contract_payload()
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
    env_names = _collect_named_entries(environment)
    env_values = _collect_env_values(environment)
    expected_worker_env = {
        entry["name"] for entry in contract["worker_template"]["env"]
    }
    assert expected_worker_env.issubset(env_names)
    assert set(contract["worker_template"]["forbidden_env_vars"]).isdisjoint(
        env_names
    )
    expected_worker_literal_values = {
        entry["name"]: entry["value"]
        for entry in contract["worker_template"]["env"]
        if entry.get("source") == "literal"
        and isinstance(entry.get("value"), str)
    }
    assert expected_worker_literal_values.items() <= env_values.items()

    expected_worker_secrets = {
        entry["name"] for entry in contract["worker_template"]["secrets"]
    }
    secrets = container.get("Secrets")
    if expected_worker_secrets:
        assert isinstance(secrets, list)
        secret_names = _collect_named_entries(secrets)
        assert secret_names == expected_worker_secrets
    else:
        assert secrets is None
    parameters = worker_template["Parameters"]
    assert isinstance(parameters, dict)
    assert "JobsTableName" in parameters
    assert "JobsTableArn" in parameters
    assert "ActivityTableName" in parameters
    assert "ActivityTableArn" in parameters
    assert ("JobsWorkerUpdateTokenSecretArn" in parameters) == bool(
        expected_worker_secrets
    )
    assert "WorkerCommand" not in parameters
    assert "SyncProcessingMaxBytes" not in parameters
    assert "TaskRoleArn: !GetAtt WorkerTaskRole.Arn" in worker_text

    worker_service = resources["WorkerService"]
    assert isinstance(worker_service, dict)
    worker_service_properties = worker_service["Properties"]
    assert isinstance(worker_service_properties, dict)
    assert worker_service_properties["EnableExecuteCommand"] is True

    required_exec_actions = {
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel",
    }

    worker_exec_policy = resources["WorkerEcsExecTaskPolicy"]
    assert isinstance(worker_exec_policy, dict)
    worker_exec_policy_doc = worker_exec_policy["Properties"]["PolicyDocument"]
    assert isinstance(worker_exec_policy_doc, dict)
    worker_exec_statements = worker_exec_policy_doc["Statement"]
    assert isinstance(worker_exec_statements, list)
    assert len(worker_exec_statements) == 1
    worker_exec_statement = worker_exec_statements[0]
    assert isinstance(worker_exec_statement, dict)
    worker_exec_actions = worker_exec_statement["Action"]
    assert isinstance(worker_exec_actions, list)
    assert set(worker_exec_actions) == required_exec_actions
    assert worker_exec_statement["Resource"] == "*"

    worker_task_policy = resources["WorkerTaskPolicy"]
    assert isinstance(worker_task_policy, dict)
    worker_task_policy_doc = worker_task_policy["Properties"]["PolicyDocument"]
    assert isinstance(worker_task_policy_doc, dict)
    worker_task_statements = worker_task_policy_doc["Statement"]
    assert isinstance(worker_task_statements, list)

    dynamo_statement = next(
        statement
        for statement in worker_task_statements
        if isinstance(statement, dict)
        and statement.get("Sid") == "WorkerDirectPersistenceDynamoTables"
    )
    dynamo_actions = dynamo_statement["Action"]
    assert isinstance(dynamo_actions, list)
    assert set(dynamo_actions) == {
        "dynamodb:ConditionCheckItem",
        "dynamodb:DeleteItem",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:UpdateItem",
    }
    assert dynamo_statement["Resource"] == [
        "JobsTableArn",
        "${JobsTableArn}/index/*",
        "ActivityTableArn",
        "${ActivityTableArn}/index/*",
    ]

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
    service_env_names = _collect_named_entries(service_environment)
    expected_service_env = {
        entry["name"] for entry in contract["service_template"]["env"]
    }
    assert expected_service_env.issubset(service_env_names)
    assert set(contract["service_template"]["forbidden_env_vars"]).isdisjoint(
        service_env_names
    )

    service_secrets = service_container["Secrets"]
    assert isinstance(service_secrets, list)
    service_secret_names = _collect_named_entries(service_secrets)
    expected_service_secrets = {
        entry["name"] for entry in contract["service_template"]["secrets"]
    }
    assert service_secret_names == expected_service_secrets

    service_parameters = service_template["Parameters"]
    assert isinstance(service_parameters, dict)
    for forbidden_parameter in contract["service_template"][
        "forbidden_parameters"
    ]:
        assert forbidden_parameter not in service_parameters
    assert "JobsQueueUrl" in service_parameters
    assert "JobsTableName" in service_parameters
    assert "ActivityTableName" in service_parameters
    assert "CacheRedisUrlSecretArn" in service_parameters
    assert "TaskRoleArn: !GetAtt ECSTaskRole.Arn" in service_text
    assert "TaskRoleArn: !Ref TaskRole" not in service_text

    ecs_service = service_resources["ECSService"]
    assert isinstance(ecs_service, dict)
    ecs_service_properties = ecs_service["Properties"]
    assert isinstance(ecs_service_properties, dict)
    assert ecs_service_properties["EnableExecuteCommand"] is True

    assert "AppSecretKeySecret" not in service_resources
    assert "ECSTaskPolicy" not in service_resources

    execution_policy = service_resources["EcsTaskExecutionSecretsPolicy"]
    assert isinstance(execution_policy, dict)
    execution_policy_doc = execution_policy["Properties"]["PolicyDocument"]
    assert isinstance(execution_policy_doc, dict)
    execution_statements = execution_policy_doc["Statement"]
    assert isinstance(execution_statements, list)
    execution_actions = {
        action
        for statement in execution_statements
        if isinstance(statement, dict)
        for action in (
            statement.get("Action", [])
            if isinstance(statement.get("Action"), list)
            else [statement.get("Action")]
        )
        if isinstance(action, str)
    }
    assert execution_actions == {
        "secretsmanager:GetSecretValue",
        "kms:Decrypt",
    }
    assert "ssm:GetParameters" not in execution_actions
    for statement in execution_statements:
        if not isinstance(statement, dict):
            continue
        actions = statement.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        resource = statement.get("Resource")
        if "secretsmanager:GetSecretValue" in actions:
            assert resource == ["CacheRedisUrlSecretArn"]
            continue
        if "kms:Decrypt" in actions:
            assert resource == "*"
            condition = statement.get("Condition")
            assert isinstance(condition, dict)
            kms_via_service = "secretsmanager.${AWS::Region}.${AWS::URLSuffix}"
            assert condition == {
                "StringEquals": {"kms:ViaService": kms_via_service}
            }
            continue
        assert resource not in {None, "*"}
        if isinstance(resource, (list, str)):
            assert "*" not in resource

    service_exec_policy = service_resources["EcsExecTaskPolicy"]
    assert isinstance(service_exec_policy, dict)
    service_exec_policy_doc = service_exec_policy["Properties"][
        "PolicyDocument"
    ]
    assert isinstance(service_exec_policy_doc, dict)
    service_exec_statements = service_exec_policy_doc["Statement"]
    assert isinstance(service_exec_statements, list)
    assert len(service_exec_statements) == 1
    service_exec_statement = service_exec_statements[0]
    assert isinstance(service_exec_statement, dict)
    service_exec_actions = service_exec_statement["Action"]
    assert isinstance(service_exec_actions, list)
    assert set(service_exec_actions) == required_exec_actions
    assert service_exec_statement["Resource"] == "*"

    for policy_name in [
        "FileTransferTaskPolicy",
        "FileTransferAsyncTaskPolicy",
    ]:
        policy = service_resources[policy_name]
        assert isinstance(policy, dict)
        policy_doc = policy["Properties"]["PolicyDocument"]
        assert isinstance(policy_doc, dict)
        policy_statements = policy_doc["Statement"]
        assert isinstance(policy_statements, list)
        for statement in policy_statements:
            assert isinstance(statement, dict)
            actions = statement.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            for action in actions:
                assert isinstance(action, str)
                assert action not in {"s3:*", "dynamodb:*", "kms:*"}, (
                    f"{policy_name} must not use broad wildcard actions: "
                    f"{statement!r}"
                )
            resource = statement.get("Resource")
            if resource == "*" or (
                isinstance(resource, list) and "*" in resource
            ):
                sid = statement.get("Sid")
                assert sid == "FileTransferKms", (
                    "Unexpected wildcard resource in "
                    f"{policy_name}: {statement!r}"
                )
                condition = statement.get("Condition")
                assert isinstance(condition, dict)
                assert "ForAnyValue:StringLike" in condition

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
    assert "IdempotencyRequiresSharedCache:" in service_text
    assert (
        "FileTransferJobsQueueArn, FileTransferJobsTableArn, and"
        in service_text
    )
    assert "JobsQueueUrl, JobsTableName, and ActivityTableName" in service_text
    assert "CacheRedisUrlSecretArn is required" in service_text
    assert (
        'IdempotencyEnabled requires FileTransferCacheEnabled to be "true"'
        in service_text
    )
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

    min_block = section_text(
        worker_text,
        "  WorkerMinTaskCount:\n",
        "  WorkerMaxTaskCount:\n",
    )
    max_block = section_text(
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


def test_runtime_ecr_lifecycle_policy_keeps_current_and_rollback_images() -> (
    None
):
    """ECR lifecycle policy must keep the current image plus one rollback."""
    text = _read("infra/runtime/ecr.yml")

    for required in [
        '"rulePriority": 1',
        '"tagStatus": "untagged"',
        '"countType": "sinceImagePushed"',
        '"countUnit": "days"',
        '"countNumber": 1',
        '"rulePriority": 2',
        '"tagStatus": "any"',
        '"countType": "imageCountMoreThan"',
        '"countNumber": 2',
        "Expire untagged images after 1 day",
        "Keep the current image and one rollback image",
    ]:
        assert required in text


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


def test_ecs_service_auth_contracts() -> None:
    """ECS service template must expose only bearer-JWT auth wiring/env vars."""
    text = _read("infra/runtime/ecs/service.yml")

    for token in [
        "OidcIssuer:",
        "OidcAudience:",
        "OidcJwksUrl:",
        "- Name: OIDC_ISSUER",
        "- Name: OIDC_AUDIENCE",
        "- Name: OIDC_JWKS_URL",
    ]:
        assert token in text

    for token in [
        "jwt_remote",
        "RemoteAuthBaseUrl:",
        "RemoteAuthTimeoutSeconds:",
        "JwtRemoteAuthParamsProvided:",
        "REMOTE_AUTH_BASE_URL",
        "REMOTE_AUTH_TIMEOUT_SECONDS",
        "OidcVerifierThreadTokens",
        "OIDC_VERIFIER_THREAD_TOKENS",
    ]:
        assert token not in text


def test_release_buildspec_single_digest_contracts() -> None:
    """Release buildspec must publish the single surviving workload digest."""
    text = _read("buildspecs/buildspec-release.yml")

    for token in [
        'python: "3.13"',
        "uv sync --locked --all-packages --all-extras --dev",
        "FILE_IMAGE_DIGEST",
        "FILE_DOCKERFILE_PATH",
        'FILE_IMAGE_TAG="file-${IMAGE_TAG}"',
        "docker build \\",
        'docker push "${ECR_REPOSITORY_URI}:${FILE_IMAGE_TAG}"',
        'FILE_IMAGE_DIGEST="${FILE_DIGEST}"',
    ]:
        assert token in text

    for token in [
        'python: "3.12"',
        "uv sync --frozen",
        "AUTH_IMAGE_DIGEST",
        "AUTH_DOCKERFILE_PATH",
        'AUTH_IMAGE_TAG="auth-${IMAGE_TAG}"',
        'docker push "${ECR_REPOSITORY_URI}:${AUTH_IMAGE_TAG}"',
        'AUTH_IMAGE_DIGEST="${AUTH_DIGEST}"',
    ]:
        assert token not in text


def test_pipeline_single_digest_promotion_contract() -> None:
    """Pipeline must promote the file workload digest without a selector."""
    text = _read("infra/nova/nova-ci-cd.yml")

    def _stage_block(start_token: str, end_token: str) -> str:
        start = text.index(start_token)
        end = text.index(end_token, start)
        return text[start:end]

    for stage_text, stage_name in [
        (_stage_block("- Name: DeployDev", "- Name: ValidateDev"), "DeployDev"),
        (
            _stage_block("- Name: DeployProd", "- Name: ValidateProd"),
            "DeployProd",
        ),
    ]:
        assert "FILE_IMAGE_DIGEST" in stage_text, stage_name
        assert "#{ReleaseBuild.FILE_IMAGE_DIGEST}" in stage_text, stage_name

    for token in [
        "DeployImageDigestVariable:",
        "AUTH_IMAGE_DIGEST",
        "UseAuthImageDigestVariable:",
        "#{ReleaseBuild.AUTH_IMAGE_DIGEST}",
    ]:
        assert token not in text


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
        "cloudfront:GetDistribution",
        "cloudfront:GetVpcOrigin",
        "ecs:DescribeClusters",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeRules",
        "wafv2:GetWebACLForResource",
        "iam:GetRole",
    ]:
        assert token in text
