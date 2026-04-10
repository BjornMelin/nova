"""Storage, state, and transfer-policy builders for the runtime stack."""

from __future__ import annotations

import json
from dataclasses import dataclass

from aws_cdk import (
    Duration,
    RemovalPolicy,
    aws_appconfig as appconfig,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
)
from constructs import Construct

from nova_runtime_support.transfer_policy_document import (
    TransferPolicyDocument,
)

from .runtime_naming import appconfig_resource_tags
from .runtime_release_manifest import build_default_transfer_policy_document


@dataclass(frozen=True)
class RuntimeStateResources:
    """DynamoDB and S3 resources used by the runtime control plane."""

    activity_table: dynamodb.Table
    export_copy_parts_table: dynamodb.Table
    export_table: dynamodb.Table
    file_bucket: s3.Bucket
    idempotency_table: dynamodb.Table
    transfer_usage_table: dynamodb.Table
    upload_sessions_table: dynamodb.Table


@dataclass(frozen=True)
class TransferPolicyResources:
    """AppConfig resources that publish the default transfer policy."""

    application: appconfig.CfnApplication
    deployment: appconfig.CfnDeployment
    environment: appconfig.CfnEnvironment
    profile: appconfig.CfnConfigurationProfile


def create_runtime_state_resources(
    scope: Construct,
    *,
    allowed_origins: list[str],
) -> RuntimeStateResources:
    """Create state tables and transfer bucket for the runtime stack."""
    export_table = dynamodb.Table(
        scope,
        "ExportsTable",
        partition_key=dynamodb.Attribute(
            name="export_id",
            type=dynamodb.AttributeType.STRING,
        ),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        point_in_time_recovery_specification=_point_in_time_recovery(),
        removal_policy=RemovalPolicy.RETAIN,
    )
    export_table.add_global_secondary_index(
        index_name="scope_id-created_at-index",
        partition_key=dynamodb.Attribute(
            name="scope_id",
            type=dynamodb.AttributeType.STRING,
        ),
        sort_key=dynamodb.Attribute(
            name="created_at",
            type=dynamodb.AttributeType.STRING,
        ),
        projection_type=dynamodb.ProjectionType.ALL,
    )

    activity_table = dynamodb.Table(
        scope,
        "ActivityTable",
        partition_key=dynamodb.Attribute(
            name="pk",
            type=dynamodb.AttributeType.STRING,
        ),
        sort_key=dynamodb.Attribute(
            name="sk",
            type=dynamodb.AttributeType.STRING,
        ),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        point_in_time_recovery_specification=_point_in_time_recovery(),
        removal_policy=RemovalPolicy.RETAIN,
    )

    idempotency_table = dynamodb.Table(
        scope,
        "IdempotencyTable",
        partition_key=dynamodb.Attribute(
            name="idempotency_key",
            type=dynamodb.AttributeType.STRING,
        ),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        time_to_live_attribute="expires_at",
        point_in_time_recovery_specification=_point_in_time_recovery(),
        removal_policy=RemovalPolicy.RETAIN,
    )
    upload_sessions_table = dynamodb.Table(
        scope,
        "UploadSessionsTable",
        partition_key=dynamodb.Attribute(
            name="session_id",
            type=dynamodb.AttributeType.STRING,
        ),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        time_to_live_attribute="resumable_until_epoch",
        point_in_time_recovery_specification=_point_in_time_recovery(),
        removal_policy=RemovalPolicy.RETAIN,
    )
    transfer_usage_table = dynamodb.Table(
        scope,
        "TransferUsageTable",
        partition_key=dynamodb.Attribute(
            name="scope_id",
            type=dynamodb.AttributeType.STRING,
        ),
        sort_key=dynamodb.Attribute(
            name="window_key",
            type=dynamodb.AttributeType.STRING,
        ),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        time_to_live_attribute="expires_at",
        point_in_time_recovery_specification=_point_in_time_recovery(),
        removal_policy=RemovalPolicy.RETAIN,
    )
    export_copy_parts_table = dynamodb.Table(
        scope,
        "ExportCopyPartsTable",
        partition_key=dynamodb.Attribute(
            name="export_id",
            type=dynamodb.AttributeType.STRING,
        ),
        sort_key=dynamodb.Attribute(
            name="part_number",
            type=dynamodb.AttributeType.NUMBER,
        ),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        time_to_live_attribute="expires_at_epoch",
        point_in_time_recovery_specification=_point_in_time_recovery(),
        removal_policy=RemovalPolicy.RETAIN,
    )
    file_bucket = s3.Bucket(
        scope,
        "FileTransferBucket",
        encryption=s3.BucketEncryption.S3_MANAGED,
        enforce_ssl=True,
        block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        transfer_acceleration=True,
        versioned=True,
        lifecycle_rules=[
            s3.LifecycleRule(
                abort_incomplete_multipart_upload_after=Duration.days(7),
                enabled=True,
                id="abort-incomplete-multipart-uploads",
            ),
            s3.LifecycleRule(
                enabled=True,
                expiration=Duration.days(3),
                id="expire-transient-workflow-artifacts",
                prefix="tmp/",
            ),
        ],
        removal_policy=RemovalPolicy.RETAIN,
        cors=[
            s3.CorsRule(
                allowed_headers=["*"],
                allowed_methods=[
                    s3.HttpMethods.GET,
                    s3.HttpMethods.PUT,
                    s3.HttpMethods.POST,
                    s3.HttpMethods.HEAD,
                ],
                allowed_origins=allowed_origins,
                exposed_headers=["ETag"],
            )
        ],
    )
    return RuntimeStateResources(
        activity_table=activity_table,
        export_copy_parts_table=export_copy_parts_table,
        export_table=export_table,
        file_bucket=file_bucket,
        idempotency_table=idempotency_table,
        transfer_usage_table=transfer_usage_table,
        upload_sessions_table=upload_sessions_table,
    )


def create_transfer_policy_resources(
    scope: Construct,
    *,
    deployment_environment: str,
) -> TransferPolicyResources:
    """Create AppConfig resources for the effective transfer policy."""
    transfer_policy_document = build_default_transfer_policy_document()
    application = appconfig.CfnApplication(
        scope,
        "TransferPolicyApplication",
        name=f"nova-transfer-policy-{deployment_environment}",
        description="Nova transfer control-plane policy",
        tags=appconfig_resource_tags(deployment_environment),
    )
    environment = appconfig.CfnEnvironment(
        scope,
        "TransferPolicyEnvironment",
        application_id=application.ref,
        name=deployment_environment,
        description="Nova runtime environment",
        tags=appconfig_resource_tags(deployment_environment),
    )
    profile = appconfig.CfnConfigurationProfile(
        scope,
        "TransferPolicyProfile",
        application_id=application.ref,
        location_uri="hosted",
        name="transfer-policy",
        tags=appconfig_resource_tags(deployment_environment),
        type="AWS.Freeform",
        validators=[
            appconfig.CfnConfigurationProfile.ValidatorsProperty(
                type="JSON_SCHEMA",
                content=json.dumps(TransferPolicyDocument.model_json_schema()),
            )
        ],
    )
    version = appconfig.CfnHostedConfigurationVersion(
        scope,
        "TransferPolicyHostedVersion",
        application_id=application.ref,
        configuration_profile_id=profile.ref,
        content=json.dumps(
            transfer_policy_document.model_dump(exclude_none=True)
        ),
        content_type="application/json",
        description="Default Nova transfer policy",
    )
    strategy = appconfig.CfnDeploymentStrategy(
        scope,
        "TransferPolicyDeploymentStrategy",
        name=f"nova-transfer-policy-{deployment_environment}",
        deployment_duration_in_minutes=15,
        final_bake_time_in_minutes=5,
        growth_factor=50,
        growth_type="LINEAR",
        replicate_to="NONE",
        tags=appconfig_resource_tags(deployment_environment),
    )
    deployment = appconfig.CfnDeployment(
        scope,
        "TransferPolicyDeployment",
        application_id=application.ref,
        configuration_profile_id=profile.ref,
        configuration_version=version.ref,
        deployment_strategy_id=strategy.ref,
        description="Deploy Nova transfer policy",
        environment_id=environment.ref,
        tags=appconfig_resource_tags(deployment_environment),
    )
    deployment.node.add_dependency(version)
    deployment.node.add_dependency(environment)
    return TransferPolicyResources(
        application=application,
        deployment=deployment,
        environment=environment,
        profile=profile,
    )


def _point_in_time_recovery() -> dynamodb.PointInTimeRecoverySpecification:
    """Return the canonical PITR setting for runtime DynamoDB tables."""
    return dynamodb.PointInTimeRecoverySpecification(
        point_in_time_recovery_enabled=True
    )
