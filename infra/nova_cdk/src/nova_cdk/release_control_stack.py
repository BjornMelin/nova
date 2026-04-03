# mypy: disable-error-code=import-not-found

"""CDK stack for the Nova AWS-native post-merge release control plane."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_iam as iam,
    aws_logs as logs,
    aws_s3 as s3,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
)
from constructs import Construct

from .runtime_stack import (
    _optional_context_or_env_value,
    _required_context_or_env_value,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PIPELINE_NAME = "nova-release-control-plane"


def _required_value(scope: Construct, *, key: str, env_var: str) -> str:
    return _required_context_or_env_value(scope, key=key, env_var=env_var)


def _optional_value(scope: Construct, *, key: str, env_var: str) -> str | None:
    raw = _optional_context_or_env_value(scope, key=key, env_var=env_var)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


@dataclass(frozen=True)
class ReleaseEnvironmentConfig:
    """One runtime deployment environment config for the release pipeline."""

    name: str
    stack_id: str
    cfn_execution_role_arn: str
    runtime_config_parameter_name: str


@dataclass(frozen=True)
class ReleaseControlInputs:
    """Resolved stack inputs for the AWS-native release control plane."""

    github_owner: str
    github_repo: str
    github_branch: str
    connection_arn: str
    codeartifact_domain: str
    codeartifact_staging_repository: str
    codeartifact_prod_repository: str
    release_signing_secret_id: str
    dev: ReleaseEnvironmentConfig
    prod: ReleaseEnvironmentConfig
    approval_email: str | None


def _load_environment_config(
    scope: Construct,
    *,
    prefix: str,
    default_name: str,
    default_stack_id: str,
    cfn_execution_role_arn: str | None = None,
) -> ReleaseEnvironmentConfig:
    """Load one prefixed release-environment configuration block."""
    env_key = f"{prefix}_runtime_environment"
    env_var = env_key.upper()
    return ReleaseEnvironmentConfig(
        name=_optional_value(scope, key=env_key, env_var=env_var)
        or default_name,
        stack_id=_optional_value(
            scope,
            key=f"{prefix}_runtime_stack_id",
            env_var=f"{prefix.upper()}_RUNTIME_STACK_ID",
        )
        or default_stack_id,
        cfn_execution_role_arn=cfn_execution_role_arn
        or _required_value(
            scope,
            key=f"{prefix}_runtime_cfn_execution_role_arn",
            env_var=f"{prefix.upper()}_RUNTIME_CFN_EXECUTION_ROLE_ARN",
        ),
        runtime_config_parameter_name=_required_value(
            scope,
            key=f"{prefix}_runtime_config_parameter_name",
            env_var=f"{prefix.upper()}_RUNTIME_CONFIG_PARAMETER_NAME",
        ),
    )


def load_release_control_inputs(
    scope: Construct,
    *,
    dev_cfn_execution_role_arn: str | None = None,
    prod_cfn_execution_role_arn: str | None = None,
) -> ReleaseControlInputs:
    """Resolve required stack inputs from CDK context or environment."""
    return ReleaseControlInputs(
        github_owner=_required_value(
            scope,
            key="release_github_owner",
            env_var="RELEASE_GITHUB_OWNER",
        ),
        github_repo=_required_value(
            scope,
            key="release_github_repo",
            env_var="RELEASE_GITHUB_REPO",
        ),
        github_branch=_optional_value(
            scope,
            key="release_github_branch",
            env_var="RELEASE_GITHUB_BRANCH",
        )
        or "main",
        connection_arn=_required_value(
            scope,
            key="release_connection_arn",
            env_var="RELEASE_CONNECTION_ARN",
        ),
        codeartifact_domain=_required_value(
            scope,
            key="codeartifact_domain",
            env_var="CODEARTIFACT_DOMAIN",
        ),
        codeartifact_staging_repository=_required_value(
            scope,
            key="codeartifact_staging_repository",
            env_var="CODEARTIFACT_STAGING_REPOSITORY",
        ),
        codeartifact_prod_repository=_required_value(
            scope,
            key="codeartifact_prod_repository",
            env_var="CODEARTIFACT_PROD_REPOSITORY",
        ),
        release_signing_secret_id=_required_value(
            scope,
            key="release_signing_secret_id",
            env_var="RELEASE_SIGNING_SECRET_ID",
        ),
        dev=_load_environment_config(
            scope,
            prefix="dev",
            default_name="dev",
            default_stack_id="NovaRuntimeStack",
            cfn_execution_role_arn=dev_cfn_execution_role_arn,
        ),
        prod=_load_environment_config(
            scope,
            prefix="prod",
            default_name="prod",
            default_stack_id="NovaRuntimeProdStack",
            cfn_execution_role_arn=prod_cfn_execution_role_arn,
        ),
        approval_email=_optional_value(
            scope,
            key="release_approval_email",
            env_var="RELEASE_APPROVAL_EMAIL",
        ),
    )


class NovaReleaseControlPlaneStack(Stack):
    """Provision the AWS-native post-merge release pipeline for Nova."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        inputs: ReleaseControlInputs | None = None,
        **kwargs: object,
    ) -> None:
        """Initialize the release control-plane stack."""
        super().__init__(scope, construct_id, **kwargs)

        inputs = inputs or load_release_control_inputs(self)

        release_artifact_bucket = s3.Bucket(
            self,
            "ReleaseArtifactBucket",
            versioned=True,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    abort_incomplete_multipart_upload_after=Duration.days(7),
                    enabled=True,
                    id="abort-incomplete-multipart-uploads",
                ),
                s3.LifecycleRule(
                    enabled=True,
                    expiration=Duration.days(180),
                    id="expire-current-release-artifacts",
                ),
                s3.LifecycleRule(
                    enabled=True,
                    id="expire-noncurrent-release-artifacts",
                    noncurrent_version_expiration=Duration.days(30),
                ),
            ],
        )
        release_manifest_bucket = s3.Bucket(
            self,
            "ReleaseManifestBucket",
            versioned=True,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    abort_incomplete_multipart_upload_after=Duration.days(7),
                    enabled=True,
                    id="abort-incomplete-multipart-manifest-uploads",
                ),
                s3.LifecycleRule(
                    enabled=True,
                    id="expire-noncurrent-release-manifests",
                    noncurrent_version_expiration=Duration.days(30),
                ),
            ],
        )
        pipeline_artifact_bucket = s3.Bucket(
            self,
            "ReleasePipelineArtifactBucket",
            versioned=True,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    abort_incomplete_multipart_upload_after=Duration.days(7),
                    enabled=True,
                    id="abort-incomplete-multipart-pipeline-uploads",
                ),
                s3.LifecycleRule(
                    enabled=True,
                    expiration=Duration.days(30),
                    id="expire-current-pipeline-artifacts",
                ),
                s3.LifecycleRule(
                    enabled=True,
                    id="expire-noncurrent-pipeline-artifacts",
                    noncurrent_version_expiration=Duration.days(30),
                ),
            ],
        )

        approval_topic: sns.Topic | None = None
        if inputs.approval_email is not None:
            approval_topic = sns.Topic(
                self,
                "ReleaseApprovalTopic",
                display_name="Nova release prod approval",
            )
            approval_topic.add_subscription(
                sns_subscriptions.EmailSubscription(inputs.approval_email)
            )

        source_artifact = codepipeline.Artifact("SourceArtifact")

        validate_project = self._build_project(
            "ValidateReleasePrepProject",
            buildspec_path="infra/nova_cdk/buildspecs/release-validate.yml",
            environment_variables={},
        )
        publish_project = self._build_project(
            "PublishAndDeployDevProject",
            buildspec_path=(
                "infra/nova_cdk/buildspecs/release-publish-and-deploy-dev.yml"
            ),
            environment_variables=self._common_env_vars(
                inputs=inputs,
                release_artifact_bucket=release_artifact_bucket.bucket_name,
                release_manifest_bucket=release_manifest_bucket.bucket_name,
            )
            | self._environment_env_vars(prefix="DEV", config=inputs.dev),
        )
        promote_project = self._build_project(
            "PromoteAndDeployProdProject",
            buildspec_path=(
                "infra/nova_cdk/buildspecs/release-promote-and-deploy-prod.yml"
            ),
            environment_variables=self._common_env_vars(
                inputs=inputs,
                release_artifact_bucket=release_artifact_bucket.bucket_name,
                release_manifest_bucket=release_manifest_bucket.bucket_name,
            )
            | self._environment_env_vars(prefix="PROD", config=inputs.prod),
        )

        self._grant_release_role_permissions(
            project=validate_project,
            inputs=inputs,
            release_artifact_bucket=release_artifact_bucket,
            release_manifest_bucket=release_manifest_bucket,
        )
        self._grant_release_role_permissions(
            project=publish_project,
            inputs=inputs,
            release_artifact_bucket=release_artifact_bucket,
            release_manifest_bucket=release_manifest_bucket,
        )
        self._grant_release_role_permissions(
            project=promote_project,
            inputs=inputs,
            release_artifact_bucket=release_artifact_bucket,
            release_manifest_bucket=release_manifest_bucket,
        )

        pipeline = codepipeline.Pipeline(
            self,
            "NovaReleaseControlPlane",
            pipeline_name=_PIPELINE_NAME,
            artifact_bucket=pipeline_artifact_bucket,
            pipeline_type=codepipeline.PipelineType.V1,
            restart_execution_on_update=True,
        )
        pipeline.add_stage(
            stage_name="Source",
            actions=[
                codepipeline_actions.CodeStarConnectionsSourceAction(
                    action_name="GitHubSource",
                    owner=inputs.github_owner,
                    repo=inputs.github_repo,
                    branch=inputs.github_branch,
                    connection_arn=inputs.connection_arn,
                    output=source_artifact,
                    code_build_clone_output=True,
                    trigger_on_push=True,
                )
            ],
        )
        pipeline.add_stage(
            stage_name="ValidateReleasePrep",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name="ValidateReleasePrep",
                    project=validate_project,
                    input=source_artifact,
                )
            ],
        )
        pipeline.add_stage(
            stage_name="PublishAndDeployDev",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name="PublishAndDeployDev",
                    project=publish_project,
                    input=source_artifact,
                    environment_variables={
                        "CODEPIPELINE_EXECUTION_ID": codebuild.BuildEnvironmentVariable(  # noqa: E501
                            value="#{codepipeline.PipelineExecutionId}"
                        )
                    },
                )
            ],
        )
        pipeline.add_stage(
            stage_name="ApproveProd",
            actions=[
                codepipeline_actions.ManualApprovalAction(
                    action_name="ApproveProd",
                    notification_topic=approval_topic,
                    additional_information=(
                        "Review the staged release execution manifest and "
                        "approve prod promotion only after dev publish/deploy "
                        "evidence is satisfactory."
                    ),
                )
            ],
        )
        pipeline.add_stage(
            stage_name="PromoteAndDeployProd",
            actions=[
                codepipeline_actions.CodeBuildAction(
                    action_name="PromoteAndDeployProd",
                    project=promote_project,
                    input=source_artifact,
                    environment_variables={
                        "CODEPIPELINE_EXECUTION_ID": codebuild.BuildEnvironmentVariable(  # noqa: E501
                            value="#{codepipeline.PipelineExecutionId}"
                        )
                    },
                )
            ],
        )

        CfnOutput(
            self,
            "NovaReleasePipelineName",
            value=pipeline.pipeline_name,
        )
        CfnOutput(
            self,
            "NovaReleaseArtifactBucketName",
            value=release_artifact_bucket.bucket_name,
        )
        CfnOutput(
            self,
            "NovaReleaseManifestBucketName",
            value=release_manifest_bucket.bucket_name,
        )
        CfnOutput(
            self,
            "NovaReleaseSourceConnectionArn",
            value=inputs.connection_arn,
        )

    def _build_project(
        self,
        project_id: str,
        *,
        buildspec_path: str,
        environment_variables: dict[str, codebuild.BuildEnvironmentVariable],
    ) -> codebuild.PipelineProject:
        buildspec_object = yaml.safe_load(
            (_REPO_ROOT / buildspec_path).read_text(encoding="utf-8")
        )
        return codebuild.PipelineProject(
            self,
            project_id,
            build_spec=codebuild.BuildSpec.from_object_to_yaml(
                buildspec_object
            ),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                compute_type=codebuild.ComputeType.SMALL,
            ),
            environment_variables=environment_variables,
            logging=codebuild.LoggingOptions(
                cloud_watch=codebuild.CloudWatchLoggingOptions(
                    enabled=True,
                    log_group=logs.LogGroup(
                        self,
                        f"{project_id}Logs",
                        retention=logs.RetentionDays.ONE_MONTH,
                    ),
                )
            ),
            timeout=Duration.minutes(60),
        )

    def _common_env_vars(
        self,
        *,
        inputs: ReleaseControlInputs,
        release_artifact_bucket: str,
        release_manifest_bucket: str,
    ) -> dict[str, codebuild.BuildEnvironmentVariable]:
        def _env(value: str) -> codebuild.BuildEnvironmentVariable:
            return codebuild.BuildEnvironmentVariable(value=value)

        return {
            "AWS_REGION": _env(self.region),
            "CODEARTIFACT_DOMAIN": _env(inputs.codeartifact_domain),
            "CODEARTIFACT_STAGING_REPOSITORY": _env(
                inputs.codeartifact_staging_repository
            ),
            "CODEARTIFACT_PROD_REPOSITORY": _env(
                inputs.codeartifact_prod_repository
            ),
            "RELEASE_GITHUB_OWNER": _env(inputs.github_owner),
            "RELEASE_GITHUB_REPO": _env(inputs.github_repo),
            "RELEASE_ARTIFACT_BUCKET": _env(release_artifact_bucket),
            "RELEASE_MANIFEST_BUCKET": _env(release_manifest_bucket),
            "RELEASE_PIPELINE_NAME": _env(_PIPELINE_NAME),
            "RELEASE_SIGNING_SECRET_ID": _env(inputs.release_signing_secret_id),
        }

    def _environment_env_vars(
        self,
        *,
        prefix: str,
        config: ReleaseEnvironmentConfig,
    ) -> dict[str, codebuild.BuildEnvironmentVariable]:
        def _env(value: str) -> codebuild.BuildEnvironmentVariable:
            return codebuild.BuildEnvironmentVariable(value=value)

        return {
            f"{prefix}_RUNTIME_ENVIRONMENT": _env(config.name),
            f"{prefix}_RUNTIME_STACK_ID": _env(config.stack_id),
            f"{prefix}_RUNTIME_CFN_EXECUTION_ROLE_ARN": _env(
                config.cfn_execution_role_arn
            ),
            f"{prefix}_RUNTIME_CONFIG_PARAMETER_NAME": _env(
                config.runtime_config_parameter_name
            ),
        }

    def _grant_release_role_permissions(
        self,
        *,
        project: codebuild.PipelineProject,
        inputs: ReleaseControlInputs,
        release_artifact_bucket: s3.Bucket,
        release_manifest_bucket: s3.Bucket,
    ) -> None:
        release_artifact_bucket.grant_read_write(project)
        release_manifest_bucket.grant_read_write(project)
        bootstrap_bucket_name = (
            f"cdk-hnb659fds-assets-{self.account}-{self.region}"
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sts:GetServiceBearerToken",
                    "codeartifact:GetAuthorizationToken",
                ],
                resources=["*"],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "codeartifact:GetRepositoryEndpoint",
                    "codeartifact:PublishPackageVersion",
                    "codeartifact:ReadFromRepository",
                    "codeartifact:CopyPackageVersions",
                ],
                resources=[
                    (
                        f"arn:{self.partition}:codeartifact:{self.region}:"
                        f"{self.account}:repository/"
                        f"{inputs.codeartifact_domain}/"
                        f"{inputs.codeartifact_staging_repository}"
                    ),
                    (
                        f"arn:{self.partition}:codeartifact:{self.region}:"
                        f"{self.account}:repository/"
                        f"{inputs.codeartifact_domain}/"
                        f"{inputs.codeartifact_prod_repository}"
                    ),
                ],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "codeartifact:DescribePackageVersion",
                    "codeartifact:ListPackageVersions",
                ],
                resources=["*"],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:{self.partition}:secretsmanager:{self.region}:{self.account}:secret:{inputs.release_signing_secret_id}*"
                ],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    (
                        f"arn:{self.partition}:ssm:{self.region}:{self.account}:"
                        f"parameter{inputs.dev.runtime_config_parameter_name}"
                    ),
                    (
                        f"arn:{self.partition}:ssm:{self.region}:{self.account}:"
                        f"parameter{inputs.prod.runtime_config_parameter_name}"
                    ),
                ],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cloudformation:CreateChangeSet",
                    "cloudformation:DeleteChangeSet",
                    "cloudformation:DescribeChangeSet",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:DescribeStacks",
                    "cloudformation:ExecuteChangeSet",
                    "cloudformation:GetTemplate",
                    "cloudformation:GetTemplateSummary",
                ],
                resources=[
                    (
                        f"arn:{self.partition}:cloudformation:{self.region}:"
                        f"{self.account}:stack/{inputs.dev.stack_id}/*"
                    ),
                    (
                        f"arn:{self.partition}:cloudformation:{self.region}:"
                        f"{self.account}:stack/{inputs.prod.stack_id}/*"
                    ),
                    (
                        f"arn:{self.partition}:cloudformation:{self.region}:"
                        f"{self.account}:changeSet/*/*"
                    ),
                ],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[
                    inputs.dev.cfn_execution_role_arn,
                    inputs.prod.cfn_execution_role_arn,
                ],
                conditions={
                    "StringEquals": {
                        "iam:PassedToService": "cloudformation.amazonaws.com"
                    }
                },
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetBucketLocation",
                    "s3:GetBucketVersioning",
                    "s3:ListBucket",
                ],
                resources=[
                    f"arn:{self.partition}:s3:::{bootstrap_bucket_name}",
                ],
            )
        )
        project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:DeleteObject*",
                    "s3:GetObject*",
                    "s3:PutObject*",
                ],
                resources=[
                    f"arn:{self.partition}:s3:::{bootstrap_bucket_name}/*",
                ],
            )
        )
