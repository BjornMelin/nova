"""CDK stack for the canonical Nova runtime."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_appconfig as appconfig,
    aws_budgets as budgets,
    aws_cloudwatch as cloudwatch,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_event_sources,
    aws_logs as logs,
    aws_route53 as route53,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
)
from constructs import Construct

from nova_runtime_support.transfer_policy_document import (
    TransferPolicyDocument,
)

from .concurrency import (
    default_api_reserved_concurrency,
    default_workflow_reserved_concurrency,
    is_production_environment,
)
from .context_inputs import (
    numeric_context_or_env_value,
    optional_context_or_env_value,
    parse_bool_flag,
    parse_string_list,
    required_context_or_env_value,
    sha256_context_or_env_value,
)
from .iam import (
    grant_copy_export_permissions,
    grant_export_status_permissions,
)
from .ingress import create_regional_rest_ingress
from .observability import add_alarm_actions, create_alarm_topic
from .runtime_naming import (
    appconfig_resource_tags,
    export_copy_worker_dlq_name,
    export_copy_worker_queue_name,
    export_name_prefix,
    observability_dashboard_name,
    runtime_alarm_names,
    stage_name_for_environment,
    transfer_spend_budget_name,
)
from .runtime_release_manifest import (
    API_FUNCTION,
    FILE_TRANSFER_EXPORT_COPY_WORKER_ATTEMPTS,
    FILE_TRANSFER_EXPORT_COPY_WORKER_LEASE_SECONDS,
    FILE_TRANSFER_EXPORT_PREFIX,
    FILE_TRANSFER_UPLOAD_PREFIX,
    WORKFLOW_FUNCTIONS,
    ApiRuntimeBindings,
    WorkflowRuntimeBindings,
    build_api_lambda_environment,
    build_default_transfer_policy_document,
    build_workflow_task_environment,
    default_export_copy_max_concurrency,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _storage_lens_configuration_id(
    scope: Construct,
    *,
    deployment_environment: str,
) -> str:
    """Return the Storage Lens configuration id used for dashboard widgets."""
    raw = optional_context_or_env_value(
        scope,
        env_var="STORAGE_LENS_CONFIGURATION_ID",
        key="storage_lens_configuration_id",
    )
    if isinstance(raw, str):
        value = raw.strip()
        if value:
            return value
    return f"nova-{deployment_environment}-storage-lens"


def _reserved_concurrency_enabled(
    scope: Construct,
    *,
    deployment_environment: str,
) -> bool:
    """Return whether Lambda reserved concurrency should be configured."""
    raw = optional_context_or_env_value(
        scope,
        env_var="ENABLE_RESERVED_CONCURRENCY",
        key="enable_reserved_concurrency",
    )
    enabled = (
        True
        if raw is None
        else parse_bool_flag(raw, key="enable_reserved_concurrency")
    )
    if is_production_environment(deployment_environment) and not enabled:
        raise ValueError(
            "enable_reserved_concurrency cannot be false for production "
            "deployments."
        )
    return enabled


def _reserved_concurrency_context_or_env_value(
    scope: Construct,
    *,
    env_var: str,
    key: str,
    default: int,
) -> int:
    """Return one bounded reserved concurrency value."""
    raw = optional_context_or_env_value(scope, env_var=env_var, key=key)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return default
    if isinstance(raw, str):
        value = int(raw.strip())
    elif isinstance(raw, (int, float)):
        value = int(raw)
    else:
        raise TypeError(f"{key} must be an integer.")
    if value < 1:
        raise ValueError(f"{key} must be >= 1.")
    return value


def _reserved_concurrency_override_present(
    scope: Construct,
    *,
    env_var: str,
    key: str,
) -> bool:
    """Return whether one explicit reserved-concurrency override is set."""
    raw = optional_context_or_env_value(
        scope,
        env_var=env_var,
        key=key,
    )
    return not (raw is None or (isinstance(raw, str) and not raw.strip()))


def _point_in_time_recovery() -> dynamodb.PointInTimeRecoverySpecification:
    """Return the canonical PITR setting for runtime DynamoDB tables."""
    return dynamodb.PointInTimeRecoverySpecification(
        point_in_time_recovery_enabled=True
    )


def _runtime_log_group(
    scope: Construct,
    *,
    function_name: str,
) -> logs.LogGroup:
    """Create the retained one-month log group for one Lambda function."""
    return logs.LogGroup(
        scope,
        f"{function_name}Logs",
        retention=logs.RetentionDays.ONE_MONTH,
        removal_policy=RemovalPolicy.RETAIN,
    )


@dataclass(frozen=True)
class RuntimeStackInputs:
    """Carry canonical runtime inputs resolved from context and environment."""

    allowed_origins: list[str]
    api_reserved_concurrency: int | None
    api_stage_throttling_burst_limit: int
    api_stage_throttling_rate_limit: float
    api_domain_name: str
    certificate_arn: str
    deployment_environment: str
    enable_waf: bool
    enable_reserved_concurrency: bool
    hosted_zone_id: str
    hosted_zone_name: str
    oidc_audience: str
    oidc_issuer: str
    oidc_jwks_url: str
    waf_rate_limit: int
    waf_write_rate_limit: int
    workflow_lambda_artifact_bucket: str
    workflow_lambda_artifact_key: str
    workflow_lambda_artifact_sha256: str
    workflow_reserved_concurrency: int | None

    @classmethod
    def from_scope(cls, scope: Construct) -> RuntimeStackInputs:
        """Resolve the canonical runtime inputs for the stack."""
        deployment_environment = (
            str(
                scope.node.try_get_context("environment")
                or os.environ.get("ENVIRONMENT")
                or "dev"
            )
            .strip()
            .lower()
        )
        allowed_origins = parse_string_list(
            scope.node.try_get_context("allowed_origins")
            or os.environ.get("STACK_ALLOWED_ORIGINS"),
            key="allowed_origins",
        )
        if not allowed_origins:
            if is_production_environment(deployment_environment):
                raise ValueError(
                    "allowed_origins must be configured for production "
                    "deployments."
                )
            allowed_origins = ["*"]
        enable_reserved_concurrency = _reserved_concurrency_enabled(
            scope,
            deployment_environment=deployment_environment,
        )
        enable_waf_raw = optional_context_or_env_value(
            scope,
            env_var="ENABLE_WAF",
            key="enable_waf",
        )
        enable_waf = (
            is_production_environment(deployment_environment)
            if enable_waf_raw is None
            else parse_bool_flag(enable_waf_raw, key="enable_waf")
        )
        if is_production_environment(deployment_environment) and not enable_waf:
            raise ValueError(
                "enable_waf cannot be false for production deployments."
            )
        if not enable_reserved_concurrency and (
            _reserved_concurrency_override_present(
                scope,
                env_var="API_RESERVED_CONCURRENCY",
                key="api_reserved_concurrency",
            )
            or _reserved_concurrency_override_present(
                scope,
                env_var="WORKFLOW_RESERVED_CONCURRENCY",
                key="workflow_reserved_concurrency",
            )
        ):
            raise ValueError(
                "Reserved concurrency overrides cannot be set when "
                "enable_reserved_concurrency is false."
            )
        return cls(
            allowed_origins=allowed_origins,
            api_reserved_concurrency=(
                _reserved_concurrency_context_or_env_value(
                    scope,
                    env_var="API_RESERVED_CONCURRENCY",
                    key="api_reserved_concurrency",
                    default=default_api_reserved_concurrency(
                        deployment_environment
                    ),
                )
                if enable_reserved_concurrency
                else None
            ),
            api_stage_throttling_burst_limit=int(
                numeric_context_or_env_value(
                    scope,
                    env_var="API_STAGE_THROTTLING_BURST_LIMIT",
                    key="api_stage_throttling_burst_limit",
                    default=100,
                )
            ),
            api_stage_throttling_rate_limit=float(
                numeric_context_or_env_value(
                    scope,
                    env_var="API_STAGE_THROTTLING_RATE_LIMIT",
                    key="api_stage_throttling_rate_limit",
                    default=50,
                    allow_float=True,
                )
            ),
            api_domain_name=required_context_or_env_value(
                scope,
                env_var="API_DOMAIN_NAME",
                key="api_domain_name",
            ),
            certificate_arn=required_context_or_env_value(
                scope,
                env_var="CERTIFICATE_ARN",
                key="certificate_arn",
            ),
            deployment_environment=deployment_environment,
            enable_waf=enable_waf,
            enable_reserved_concurrency=enable_reserved_concurrency,
            hosted_zone_id=required_context_or_env_value(
                scope,
                env_var="HOSTED_ZONE_ID",
                key="hosted_zone_id",
            ),
            hosted_zone_name=required_context_or_env_value(
                scope,
                env_var="HOSTED_ZONE_NAME",
                key="hosted_zone_name",
            ),
            oidc_audience=required_context_or_env_value(
                scope,
                env_var="JWT_AUDIENCE",
                key="jwt_audience",
            ),
            oidc_issuer=required_context_or_env_value(
                scope,
                env_var="JWT_ISSUER",
                key="jwt_issuer",
            ),
            oidc_jwks_url=required_context_or_env_value(
                scope,
                env_var="JWT_JWKS_URL",
                key="jwt_jwks_url",
            ),
            waf_rate_limit=int(
                numeric_context_or_env_value(
                    scope,
                    env_var="WAF_RATE_LIMIT",
                    key="waf_rate_limit",
                    default=2000,
                    minimum=100,
                )
            ),
            waf_write_rate_limit=int(
                numeric_context_or_env_value(
                    scope,
                    env_var="WAF_WRITE_RATE_LIMIT",
                    key="waf_write_rate_limit",
                    default=500,
                    minimum=100,
                )
            ),
            workflow_lambda_artifact_bucket=required_context_or_env_value(
                scope,
                env_var="WORKFLOW_LAMBDA_ARTIFACT_BUCKET",
                key="workflow_lambda_artifact_bucket",
            ),
            workflow_lambda_artifact_key=required_context_or_env_value(
                scope,
                env_var="WORKFLOW_LAMBDA_ARTIFACT_KEY",
                key="workflow_lambda_artifact_key",
            ),
            workflow_lambda_artifact_sha256=sha256_context_or_env_value(
                scope,
                env_var="WORKFLOW_LAMBDA_ARTIFACT_SHA256",
                key="workflow_lambda_artifact_sha256",
            ),
            workflow_reserved_concurrency=(
                _reserved_concurrency_context_or_env_value(
                    scope,
                    env_var="WORKFLOW_RESERVED_CONCURRENCY",
                    key="workflow_reserved_concurrency",
                    default=default_workflow_reserved_concurrency(
                        deployment_environment
                    ),
                )
                if enable_reserved_concurrency
                else None
            ),
        )


class NovaRuntimeStack(Stack):
    """Provision the canonical Nova runtime platform."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs: Any,
    ) -> None:
        """Initialize the runtime stack and its primary resources."""
        super().__init__(scope, construct_id, **kwargs)
        inputs = RuntimeStackInputs.from_scope(self)

        export_table = dynamodb.Table(
            self,
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
            self,
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
            self,
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
            self,
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
            self,
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
            self,
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
        export_copy_worker_attempts = FILE_TRANSFER_EXPORT_COPY_WORKER_ATTEMPTS
        export_copy_worker_lease_seconds = (
            FILE_TRANSFER_EXPORT_COPY_WORKER_LEASE_SECONDS
        )
        export_copy_max_concurrency = default_export_copy_max_concurrency(
            inputs.workflow_reserved_concurrency
        )
        export_copy_dlq = sqs.Queue(
            self,
            "ExportCopyWorkerDlq",
            queue_name=export_copy_worker_dlq_name(
                inputs.deployment_environment
            ),
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
        )
        export_copy_queue = sqs.Queue(
            self,
            "ExportCopyWorkerQueue",
            queue_name=export_copy_worker_queue_name(
                inputs.deployment_environment
            ),
            dead_letter_queue=sqs.DeadLetterQueue(
                queue=export_copy_dlq,
                max_receive_count=export_copy_worker_attempts,
            ),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            receive_message_wait_time=Duration.seconds(20),
            # Visibility covers handler work; matches worker lease seconds.
            visibility_timeout=Duration.seconds(
                export_copy_worker_lease_seconds
            ),
        )
        file_bucket = s3.Bucket(
            self,
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
                    allowed_origins=inputs.allowed_origins,
                    exposed_headers=["ETag"],
                )
            ],
        )
        transfer_policy_document = build_default_transfer_policy_document()
        transfer_policy_application = appconfig.CfnApplication(
            self,
            "TransferPolicyApplication",
            name=f"nova-transfer-policy-{inputs.deployment_environment}",
            description="Nova transfer control-plane policy",
            tags=appconfig_resource_tags(inputs.deployment_environment),
        )
        transfer_policy_environment = appconfig.CfnEnvironment(
            self,
            "TransferPolicyEnvironment",
            application_id=transfer_policy_application.ref,
            name=inputs.deployment_environment,
            description="Nova runtime environment",
            tags=appconfig_resource_tags(inputs.deployment_environment),
        )
        transfer_policy_profile = appconfig.CfnConfigurationProfile(
            self,
            "TransferPolicyProfile",
            application_id=transfer_policy_application.ref,
            location_uri="hosted",
            name="transfer-policy",
            tags=appconfig_resource_tags(inputs.deployment_environment),
            type="AWS.Freeform",
            validators=[
                appconfig.CfnConfigurationProfile.ValidatorsProperty(
                    type="JSON_SCHEMA",
                    content=json.dumps(
                        TransferPolicyDocument.model_json_schema()
                    ),
                )
            ],
        )
        transfer_policy_version = appconfig.CfnHostedConfigurationVersion(
            self,
            "TransferPolicyHostedVersion",
            application_id=transfer_policy_application.ref,
            configuration_profile_id=transfer_policy_profile.ref,
            content=json.dumps(
                transfer_policy_document.model_dump(exclude_none=True)
            ),
            content_type="application/json",
            description="Default Nova transfer policy",
        )
        transfer_policy_strategy = appconfig.CfnDeploymentStrategy(
            self,
            "TransferPolicyDeploymentStrategy",
            name=f"nova-transfer-policy-{inputs.deployment_environment}",
            deployment_duration_in_minutes=15,
            final_bake_time_in_minutes=5,
            growth_factor=50,
            growth_type="LINEAR",
            replicate_to="NONE",
            tags=appconfig_resource_tags(inputs.deployment_environment),
        )
        transfer_policy_deployment = appconfig.CfnDeployment(
            self,
            "TransferPolicyDeployment",
            application_id=transfer_policy_application.ref,
            configuration_profile_id=transfer_policy_profile.ref,
            configuration_version=transfer_policy_version.ref,
            deployment_strategy_id=transfer_policy_strategy.ref,
            description="Deploy Nova transfer policy",
            environment_id=transfer_policy_environment.ref,
            tags=appconfig_resource_tags(inputs.deployment_environment),
        )
        transfer_policy_deployment.node.add_dependency(transfer_policy_version)
        transfer_policy_deployment.node.add_dependency(
            transfer_policy_environment
        )

        workflow_bindings = WorkflowRuntimeBindings(
            file_transfer_bucket=file_bucket.bucket_name,
            upload_sessions_table=upload_sessions_table.table_name,
            transfer_usage_table=transfer_usage_table.table_name,
            exports_dynamodb_table=export_table.table_name,
            export_copy_parts_table=export_copy_parts_table.table_name,
            export_copy_queue_url=export_copy_queue.queue_url,
        )
        task_env = build_workflow_task_environment(
            bindings=workflow_bindings,
            export_copy_max_concurrency=export_copy_max_concurrency,
        )
        workflow_artifact_bucket = s3.Bucket.from_bucket_name(
            self,
            "WorkflowLambdaArtifactBucket",
            inputs.workflow_lambda_artifact_bucket,
        )
        workflow_fn_props = {
            "code": lambda_.Code.from_bucket(
                workflow_artifact_bucket,
                inputs.workflow_lambda_artifact_key,
            ),
            "architecture": lambda_.Architecture.ARM_64,
            "runtime": lambda_.Runtime.PYTHON_3_13,
            "timeout": Duration.minutes(5),
            "memory_size": 1024,
            "tracing": lambda_.Tracing.ACTIVE,
        }
        if inputs.workflow_reserved_concurrency is not None:
            workflow_fn_props["reserved_concurrent_executions"] = (
                inputs.workflow_reserved_concurrency
            )

        workflow_functions: dict[str, lambda_.Function] = {}
        for authority in WORKFLOW_FUNCTIONS:
            workflow_functions[authority.logical_id] = lambda_.Function(
                self,
                authority.logical_id,
                handler=authority.handler,
                environment=task_env,
                log_group=_runtime_log_group(
                    self,
                    function_name=authority.function_name,
                ),
                **workflow_fn_props,
            )
        validate_fn = workflow_functions["ValidateExportFunction"]
        finalize_fn = workflow_functions["FinalizeExportFunction"]
        fail_fn = workflow_functions["FailExportFunction"]
        copy_fn = workflow_functions["CopyExportFunction"]
        prepare_copy_fn = workflow_functions["PrepareExportCopyFunction"]
        start_queued_copy_fn = workflow_functions[
            "StartQueuedExportCopyFunction"
        ]
        poll_queued_copy_fn = workflow_functions["PollQueuedExportCopyFunction"]
        export_copy_worker_fn = workflow_functions["ExportCopyWorkerFunction"]
        reconcile_transfer_state_fn = workflow_functions[
            "ReconcileTransferStateFunction"
        ]

        grant_export_status_permissions(
            function=validate_fn,
            export_table=export_table,
        )
        grant_export_status_permissions(
            function=finalize_fn,
            export_table=export_table,
        )
        grant_export_status_permissions(
            function=fail_fn,
            export_table=export_table,
        )
        grant_export_status_permissions(
            function=prepare_copy_fn,
            export_table=export_table,
        )
        grant_export_status_permissions(
            function=start_queued_copy_fn,
            export_table=export_table,
        )
        grant_export_status_permissions(
            function=poll_queued_copy_fn,
            export_table=export_table,
        )
        grant_copy_export_permissions(
            function=copy_fn,
            export_table=export_table,
            file_bucket=file_bucket,
            export_prefix=FILE_TRANSFER_EXPORT_PREFIX,
            upload_prefix=FILE_TRANSFER_UPLOAD_PREFIX,
        )
        grant_copy_export_permissions(
            function=prepare_copy_fn,
            export_table=export_table,
            file_bucket=file_bucket,
            export_prefix=FILE_TRANSFER_EXPORT_PREFIX,
            upload_prefix=FILE_TRANSFER_UPLOAD_PREFIX,
        )
        grant_copy_export_permissions(
            function=start_queued_copy_fn,
            export_table=export_table,
            file_bucket=file_bucket,
            export_prefix=FILE_TRANSFER_EXPORT_PREFIX,
            upload_prefix=FILE_TRANSFER_UPLOAD_PREFIX,
        )
        grant_copy_export_permissions(
            function=poll_queued_copy_fn,
            export_table=export_table,
            file_bucket=file_bucket,
            export_prefix=FILE_TRANSFER_EXPORT_PREFIX,
            upload_prefix=FILE_TRANSFER_UPLOAD_PREFIX,
        )
        grant_copy_export_permissions(
            function=export_copy_worker_fn,
            export_table=export_table,
            file_bucket=file_bucket,
            export_prefix=FILE_TRANSFER_EXPORT_PREFIX,
            upload_prefix=FILE_TRANSFER_UPLOAD_PREFIX,
        )
        export_copy_parts_table.grant_read_write_data(start_queued_copy_fn)
        export_copy_parts_table.grant_read_write_data(poll_queued_copy_fn)
        export_copy_parts_table.grant_read_write_data(export_copy_worker_fn)
        export_copy_queue.grant_send_messages(start_queued_copy_fn)
        export_copy_queue.grant_consume_messages(export_copy_worker_fn)
        export_copy_dlq.grant_consume_messages(export_copy_worker_fn)
        export_copy_worker_fn.add_event_source(
            lambda_event_sources.SqsEventSource(
                export_copy_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(5),
                report_batch_item_failures=True,
                max_concurrency=export_copy_max_concurrency,
            )
        )
        upload_sessions_table.grant_read_write_data(reconcile_transfer_state_fn)
        transfer_usage_table.grant_read_write_data(reconcile_transfer_state_fn)
        file_bucket.grant_read_write(reconcile_transfer_state_fn)
        reconcile_transfer_state_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket", "s3:ListBucketMultipartUploads"],
                resources=[file_bucket.bucket_arn],
            )
        )
        events.Rule(
            self,
            "TransferReconciliationSchedule",
            schedule=events.Schedule.rate(Duration.hours(1)),
            targets=[targets.LambdaFunction(reconcile_transfer_state_fn)],
        )

        workflow_failure_task = tasks.LambdaInvoke(
            self,
            "PersistWorkflowFailure",
            lambda_function=fail_fn,
            payload=sfn.TaskInput.from_object(
                {
                    "export_id": sfn.JsonPath.string_at("$.export_id"),
                    "scope_id": sfn.JsonPath.string_at("$.scope_id"),
                    "source_key": sfn.JsonPath.string_at("$.source_key"),
                    "filename": sfn.JsonPath.string_at("$.filename"),
                    "status": "failed",
                    "created_at": sfn.JsonPath.string_at("$.created_at"),
                    "updated_at": sfn.JsonPath.string_at("$.updated_at"),
                    "error": sfn.JsonPath.string_at("$.workflow_error.Error"),
                    "cause": sfn.JsonPath.string_at("$.workflow_error.Cause"),
                }
            ),
            payload_response_only=True,
            retry_on_service_exceptions=False,
        )
        workflow_failure = workflow_failure_task.next(
            sfn.Fail(self, "WorkflowFailed")
        )

        validate_task = tasks.LambdaInvoke(
            self,
            "ValidateExport",
            lambda_function=validate_fn,
            payload_response_only=True,
            retry_on_service_exceptions=False,
        )
        prepare_copy_task = tasks.LambdaInvoke(
            self,
            "PrepareExportCopy",
            lambda_function=prepare_copy_fn,
            payload_response_only=True,
            retry_on_service_exceptions=False,
        )
        copy_task = tasks.LambdaInvoke(
            self,
            "CopyExport",
            lambda_function=copy_fn,
            payload_response_only=True,
            retry_on_service_exceptions=False,
        )
        start_queued_copy_task = tasks.LambdaInvoke(
            self,
            "StartQueuedExportCopy",
            lambda_function=start_queued_copy_fn,
            payload_response_only=True,
            retry_on_service_exceptions=False,
        )
        poll_queued_copy_task = tasks.LambdaInvoke(
            self,
            "PollQueuedExportCopy",
            lambda_function=poll_queued_copy_fn,
            payload_response_only=True,
            retry_on_service_exceptions=False,
        )
        finalize_inline_task = tasks.LambdaInvoke(
            self,
            "FinalizeInlineExport",
            lambda_function=finalize_fn,
            payload_response_only=True,
            retry_on_service_exceptions=False,
        )
        finalize_queued_task = tasks.LambdaInvoke(
            self,
            "FinalizeQueuedExport",
            lambda_function=finalize_fn,
            payload_response_only=True,
            retry_on_service_exceptions=False,
        )

        for task in (
            validate_task,
            prepare_copy_task,
            copy_task,
            start_queued_copy_task,
            poll_queued_copy_task,
            finalize_inline_task,
            finalize_queued_task,
            workflow_failure_task,
        ):
            task.add_retry(
                errors=[
                    "Lambda.ClientExecutionTimeoutException",
                    "Lambda.ServiceException",
                    "Lambda.AWSLambdaException",
                    "Lambda.SdkClientException",
                    "Lambda.TooManyRequestsException",
                    "Lambda.Unknown",
                    "Sandbox.Timedout",
                ],
                interval=Duration.seconds(2),
                max_attempts=4,
                backoff_rate=2,
                max_delay=Duration.seconds(30),
                jitter_strategy=sfn.JitterType.FULL,
            )
            task.add_retry(
                errors=[sfn.Errors.TIMEOUT],
                interval=Duration.seconds(5),
                max_attempts=2,
                backoff_rate=2,
                max_delay=Duration.seconds(30),
                jitter_strategy=sfn.JitterType.FULL,
            )
        for task in (
            validate_task,
            prepare_copy_task,
            copy_task,
            start_queued_copy_task,
            poll_queued_copy_task,
            finalize_inline_task,
            finalize_queued_task,
        ):
            task.add_catch(workflow_failure, result_path="$.workflow_error")

        copy_strategy_choice = sfn.Choice(self, "SelectExportCopyLane")
        queued_copy_progress_choice = sfn.Choice(
            self,
            "QueuedExportCopyReady",
        )
        queued_copy_wait = sfn.Wait(
            self,
            "WaitForQueuedExportCopy",
            time=sfn.WaitTime.duration(Duration.seconds(15)),
        )
        export_completed = sfn.Succeed(self, "ExportCompleted")
        export_cancelled = sfn.Succeed(self, "ExportCancelled")

        queued_copy_chain = (
            start_queued_copy_task.next(queued_copy_wait)
            .next(poll_queued_copy_task)
            .next(
                queued_copy_progress_choice.when(
                    sfn.Condition.string_equals(
                        "$.copy_progress_state",
                        "ready",
                    ),
                    finalize_queued_task.next(export_completed),
                )
                .when(
                    sfn.Condition.string_equals(
                        "$.copy_progress_state",
                        "cancelled",
                    ),
                    export_cancelled,
                )
                .otherwise(queued_copy_wait)
            )
        )

        state_machine_log_group = logs.LogGroup(
            self,
            "ExportWorkflowLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.RETAIN,
        )
        state_machine = sfn.StateMachine(
            self,
            "ExportWorkflowStateMachine",
            state_machine_type=sfn.StateMachineType.STANDARD,
            definition_body=sfn.DefinitionBody.from_chainable(
                validate_task.next(prepare_copy_task).next(
                    copy_strategy_choice.when(
                        sfn.Condition.string_equals(
                            "$.copy_progress_state",
                            "cancelled",
                        ),
                        export_cancelled,
                    )
                    .when(
                        sfn.Condition.string_equals(
                            "$.copy_strategy",
                            "worker",
                        ),
                        queued_copy_chain,
                    )
                    .otherwise(
                        copy_task.next(finalize_inline_task).next(
                            export_completed
                        )
                    )
                )
            ),
            logs=sfn.LogOptions(
                destination=state_machine_log_group,
                level=sfn.LogLevel.ALL,
            ),
            tracing_enabled=True,
            timeout=Duration.hours(3),
        )

        api_lambda_artifact_bucket_name = required_context_or_env_value(
            self,
            env_var="API_LAMBDA_ARTIFACT_BUCKET",
            key="api_lambda_artifact_bucket",
        )
        api_lambda_artifact_key = required_context_or_env_value(
            self,
            env_var="API_LAMBDA_ARTIFACT_KEY",
            key="api_lambda_artifact_key",
        )
        api_lambda_artifact_sha256 = sha256_context_or_env_value(
            self,
            env_var="API_LAMBDA_ARTIFACT_SHA256",
            key="api_lambda_artifact_sha256",
        )
        api_lambda_artifact_bucket = s3.Bucket.from_bucket_name(
            self,
            "ApiLambdaArtifactBucket",
            api_lambda_artifact_bucket_name,
        )
        common_env = build_api_lambda_environment(
            bindings=ApiRuntimeBindings(
                file_transfer_bucket=workflow_bindings.file_transfer_bucket,
                upload_sessions_table=workflow_bindings.upload_sessions_table,
                transfer_usage_table=workflow_bindings.transfer_usage_table,
                exports_dynamodb_table=workflow_bindings.exports_dynamodb_table,
                export_copy_parts_table=(
                    workflow_bindings.export_copy_parts_table
                ),
                export_copy_queue_url=workflow_bindings.export_copy_queue_url,
                allowed_origins_json=json.dumps(inputs.allowed_origins),
                activity_rollups_table=activity_table.table_name,
                oidc_issuer=inputs.oidc_issuer,
                oidc_audience=inputs.oidc_audience,
                oidc_jwks_url=inputs.oidc_jwks_url,
                transfer_policy_appconfig_application=(
                    transfer_policy_application.ref
                ),
                transfer_policy_appconfig_environment=(
                    transfer_policy_environment.ref
                ),
                transfer_policy_appconfig_profile=transfer_policy_profile.ref,
                idempotency_dynamodb_table=idempotency_table.table_name,
                export_workflow_state_machine_arn=(
                    state_machine.state_machine_arn
                ),
                api_release_artifact_sha256=api_lambda_artifact_sha256,
            ),
            export_copy_max_concurrency=export_copy_max_concurrency,
        )

        api_function_kwargs: dict[str, Any] = {
            "runtime": lambda_.Runtime.PYTHON_3_13,
            "handler": API_FUNCTION.handler,
            "code": lambda_.Code.from_bucket(
                api_lambda_artifact_bucket,
                api_lambda_artifact_key,
            ),
            "architecture": lambda_.Architecture.ARM_64,
            "memory_size": 2048,
            "timeout": Duration.seconds(29),
            "tracing": lambda_.Tracing.ACTIVE,
            "environment": common_env,
            "log_group": _runtime_log_group(
                self,
                function_name=API_FUNCTION.function_name,
            ),
        }
        if inputs.api_reserved_concurrency is not None:
            api_function_kwargs["reserved_concurrent_executions"] = (
                inputs.api_reserved_concurrency
            )

        api_function = lambda_.Function(
            self,
            API_FUNCTION.logical_id,
            **api_function_kwargs,
        )
        file_bucket.grant_read_write(api_function)
        export_table.grant_read_write_data(api_function)
        activity_table.grant_read_write_data(api_function)
        idempotency_table.grant_read_write_data(api_function)
        upload_sessions_table.grant_read_write_data(api_function)
        transfer_usage_table.grant_read_write_data(api_function)
        state_machine.grant_start_execution(api_function)
        api_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["states:DescribeStateMachine"],
                resources=[state_machine.state_machine_arn],
            )
        )
        api_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["states:StopExecution"],
                resources=[
                    Stack.of(self).format_arn(
                        service="states",
                        resource="execution",
                        resource_name=f"{state_machine.state_machine_name}:*",
                    )
                ],
            )
        )
        api_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "appconfig:StartConfigurationSession",
                    "appconfig:GetLatestConfiguration",
                ],
                resources=["*"],
            )
        )

        ingress = create_regional_rest_ingress(
            self,
            api_domain_name=inputs.api_domain_name,
            api_handler=api_function,
            certificate_arn=inputs.certificate_arn,
            hosted_zone=route53.HostedZone.from_hosted_zone_attributes(
                self,
                "NovaHostedZone",
                hosted_zone_id=inputs.hosted_zone_id,
                zone_name=inputs.hosted_zone_name,
            ),
            stage_name=stage_name_for_environment(
                inputs.deployment_environment
            ),
            throttling_burst_limit=inputs.api_stage_throttling_burst_limit,
            throttling_rate_limit=inputs.api_stage_throttling_rate_limit,
            enable_waf=inputs.enable_waf,
            waf_rate_limit=inputs.waf_rate_limit,
            waf_write_rate_limit=inputs.waf_write_rate_limit,
        )

        alarm_topic = create_alarm_topic(
            self,
            deployment_environment=inputs.deployment_environment,
        )
        alarm_names = runtime_alarm_names(inputs.deployment_environment)
        api_lambda_errors_alarm = cloudwatch.Alarm(
            self,
            "ApiLambdaErrorsAlarm",
            alarm_name=alarm_names["api_lambda_errors"],
            metric=api_function.metric_errors(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when the API Lambda records errors.",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        api_lambda_throttles_alarm = cloudwatch.Alarm(
            self,
            "ApiLambdaThrottlesAlarm",
            alarm_name=alarm_names["api_lambda_throttles"],
            metric=api_function.metric_throttles(
                period=Duration.minutes(5),
            ),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when the API Lambda throttles.",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        api_gateway_5xx_alarm = cloudwatch.Alarm(
            self,
            "ApiGateway5xxAlarm",
            alarm_name=alarm_names["api_gateway_5xx"],
            metric=ingress.rest_api.metric_server_error(
                period=Duration.minutes(5),
            ),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when the public REST API returns 5xx.",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        api_latency_alarm = cloudwatch.Alarm(
            self,
            "ApiGatewayLatencyAlarm",
            alarm_name=alarm_names["api_latency"],
            metric=ingress.rest_api.metric_latency(
                period=Duration.minutes(5),
                statistic="p95",
            ),
            threshold=5000,
            evaluation_periods=1,
            alarm_description="Alarm when REST API p95 latency exceeds 5s.",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        workflow_task_throttles_alarm = cloudwatch.Alarm(
            self,
            "WorkflowTaskThrottlesAlarm",
            alarm_name=alarm_names["workflow_task_throttles"],
            metric=cloudwatch.MathExpression(
                expression=(
                    "validate + prepare + copy + start + poll + "
                    "finalize + fail + worker"
                ),
                period=Duration.minutes(5),
                using_metrics={
                    "validate": validate_fn.metric_throttles(
                        period=Duration.minutes(5)
                    ),
                    "prepare": prepare_copy_fn.metric_throttles(
                        period=Duration.minutes(5)
                    ),
                    "copy": copy_fn.metric_throttles(
                        period=Duration.minutes(5)
                    ),
                    "start": start_queued_copy_fn.metric_throttles(
                        period=Duration.minutes(5)
                    ),
                    "poll": poll_queued_copy_fn.metric_throttles(
                        period=Duration.minutes(5)
                    ),
                    "finalize": finalize_fn.metric_throttles(
                        period=Duration.minutes(5)
                    ),
                    "worker": export_copy_worker_fn.metric_throttles(
                        period=Duration.minutes(5)
                    ),
                    "fail": fail_fn.metric_throttles(
                        period=Duration.minutes(5)
                    ),
                },
            ),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when workflow task Lambdas throttle.",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        export_workflow_failures_alarm = cloudwatch.Alarm(
            self,
            "ExportWorkflowFailuresAlarm",
            alarm_name=alarm_names["export_workflow_failures"],
            metric=state_machine.metric_failed(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when export workflow executions fail.",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        export_workflow_timeouts_alarm = cloudwatch.Alarm(
            self,
            "ExportWorkflowTimeoutsAlarm",
            alarm_name=alarm_names["export_workflow_timeouts"],
            metric=state_machine.metric_timed_out(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when export workflow executions time out.",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        exports_table_throttles_alarm = cloudwatch.Alarm(
            self,
            "ExportsTableThrottlesAlarm",
            alarm_name=alarm_names["exports_table_throttles"],
            metric=cloudwatch.MathExpression(
                expression="get_item + put_item + query",
                period=Duration.minutes(5),
                using_metrics={
                    "get_item": (
                        export_table.metric_throttled_requests_for_operation(
                            "GetItem",
                            period=Duration.minutes(5),
                        )
                    ),
                    "put_item": (
                        export_table.metric_throttled_requests_for_operation(
                            "PutItem",
                            period=Duration.minutes(5),
                        )
                    ),
                    "query": (
                        export_table.metric_throttled_requests_for_operation(
                            "Query",
                            period=Duration.minutes(5),
                        )
                    ),
                },
            ),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when export table requests throttle.",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        upload_sessions_table_throttles_alarm = cloudwatch.Alarm(
            self,
            "UploadSessionsTableThrottlesAlarm",
            alarm_name=alarm_names["upload_sessions_table_throttles"],
            metric=cloudwatch.MathExpression(
                expression="get_item + put_item + query",
                period=Duration.minutes(5),
                using_metrics={
                    "get_item": (
                        upload_sessions_table.metric_throttled_requests_for_operation(
                            "GetItem",
                            period=Duration.minutes(5),
                        )
                    ),
                    "put_item": (
                        upload_sessions_table.metric_throttled_requests_for_operation(
                            "PutItem",
                            period=Duration.minutes(5),
                        )
                    ),
                    "query": (
                        upload_sessions_table.metric_throttled_requests_for_operation(
                            "Query",
                            period=Duration.minutes(5),
                        )
                    ),
                },
            ),
            threshold=1,
            evaluation_periods=1,
            alarm_description=(
                "Alarm when upload session table requests throttle."
            ),
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        transfer_usage_table_throttles_alarm = cloudwatch.Alarm(
            self,
            "TransferUsageTableThrottlesAlarm",
            alarm_name=alarm_names["transfer_usage_table_throttles"],
            metric=cloudwatch.MathExpression(
                expression="get_item + update_item",
                period=Duration.minutes(5),
                using_metrics={
                    "get_item": (
                        transfer_usage_table.metric_throttled_requests_for_operation(
                            "GetItem",
                            period=Duration.minutes(5),
                        )
                    ),
                    "update_item": (
                        transfer_usage_table.metric_throttled_requests_for_operation(
                            "UpdateItem",
                            period=Duration.minutes(5),
                        )
                    ),
                },
            ),
            threshold=1,
            evaluation_periods=1,
            alarm_description=(
                "Alarm when transfer usage table requests throttle."
            ),
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        upload_sessions_stale_alarm = cloudwatch.Alarm(
            self,
            "UploadSessionsStaleAlarm",
            alarm_name=alarm_names["upload_sessions_stale"],
            metric=cloudwatch.Metric(
                namespace="NovaFileApi",
                metric_name="upload_sessions_stale",
                dimensions_map={"source": "transfer_reconciliation"},
                statistic="Maximum",
                period=Duration.minutes(5),
            ),
            threshold=1,
            evaluation_periods=1,
            alarm_description=(
                "Alarm when transfer reconciliation observes stale upload "
                "sessions."
            ),
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        export_copy_worker_dlq_alarm = cloudwatch.Alarm(
            self,
            "ExportCopyWorkerDlqAlarm",
            alarm_name=alarm_names["export_copy_worker_dlq"],
            metric=export_copy_dlq.metric_approximate_number_of_messages_visible(
                period=Duration.minutes(5)
            ),
            threshold=1,
            evaluation_periods=1,
            alarm_description=(
                "Alarm when the export copy worker DLQ receives messages."
            ),
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        export_copy_worker_queue_age_alarm = cloudwatch.Alarm(
            self,
            "ExportCopyWorkerQueueAgeAlarm",
            alarm_name=alarm_names["export_copy_worker_queue_age"],
            metric=export_copy_queue.metric_approximate_age_of_oldest_message(
                period=Duration.minutes(5)
            ),
            threshold=300,
            evaluation_periods=1,
            alarm_description=(
                "Alarm when queued export copy work waits longer than "
                "5 minutes."
            ),
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        add_alarm_actions(
            alarms=[
                api_gateway_5xx_alarm,
                api_latency_alarm,
                api_lambda_errors_alarm,
                api_lambda_throttles_alarm,
                export_workflow_failures_alarm,
                export_workflow_timeouts_alarm,
                export_copy_worker_dlq_alarm,
                export_copy_worker_queue_age_alarm,
                exports_table_throttles_alarm,
                upload_sessions_table_throttles_alarm,
                upload_sessions_stale_alarm,
                transfer_usage_table_throttles_alarm,
                workflow_task_throttles_alarm,
            ],
            topic=alarm_topic,
        )
        metrics_namespace = "NovaFileApi"
        storage_lens_configuration_id = _storage_lens_configuration_id(
            self,
            deployment_environment=inputs.deployment_environment,
        )
        s3.CfnStorageLens(
            self,
            "FileTransferStorageLens",
            storage_lens_configuration=s3.CfnStorageLens.StorageLensConfigurationProperty(
                id=storage_lens_configuration_id,
                is_enabled=True,
                account_level=s3.CfnStorageLens.AccountLevelProperty(
                    activity_metrics=s3.CfnStorageLens.ActivityMetricsProperty(
                        is_enabled=True
                    ),
                    advanced_cost_optimization_metrics=s3.CfnStorageLens.AdvancedCostOptimizationMetricsProperty(
                        is_enabled=True
                    ),
                    bucket_level=s3.CfnStorageLens.BucketLevelProperty(
                        activity_metrics=s3.CfnStorageLens.ActivityMetricsProperty(
                            is_enabled=True
                        ),
                        advanced_cost_optimization_metrics=s3.CfnStorageLens.AdvancedCostOptimizationMetricsProperty(
                            is_enabled=True
                        ),
                    ),
                ),
                data_export=s3.CfnStorageLens.DataExportProperty(
                    cloud_watch_metrics=s3.CfnStorageLens.CloudWatchMetricsProperty(
                        is_enabled=True
                    )
                ),
            ),
        )
        storage_lens_dimensions = {
            "configuration_id": storage_lens_configuration_id,
            "metrics_version": "1.0",
            "aws_account_number": Stack.of(self).account,
            "aws_region": Stack.of(self).region,
            "bucket_name": file_bucket.bucket_name,
            "record_type": "BUCKET",
        }
        stale_mpu_bytes_alarm = cloudwatch.Alarm(
            self,
            "StaleMultipartUploadBytesAlarm",
            alarm_name=alarm_names["stale_multipart_upload_bytes"],
            metric=cloudwatch.Metric(
                namespace="AWS/S3/Storage-Lens",
                metric_name="IncompleteMPUStorageBytesOlderThan7Days",
                dimensions_map=storage_lens_dimensions,
                statistic="Average",
                period=Duration.days(1),
            ),
            threshold=float(1024 * 1024 * 1024),
            evaluation_periods=1,
            alarm_description=(
                "Alarm when incomplete multipart upload bytes older than "
                "7 days "
                "remain above the stale-data threshold."
            ),
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        add_alarm_actions(alarms=[stale_mpu_bytes_alarm], topic=alarm_topic)
        transfer_budget_name = transfer_spend_budget_name(
            inputs.deployment_environment
        )
        budgets.CfnBudget(
            self,
            "TransferSpendBudget",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_name=transfer_budget_name,
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(
                    amount=(
                        1000
                        if is_production_environment(
                            inputs.deployment_environment
                        )
                        else 100
                    ),
                    unit="USD",
                ),
                cost_filters={
                    "Service": [
                        "Amazon API Gateway",
                        "Amazon AppConfig",
                        "Amazon DynamoDB",
                        "Amazon Simple Storage Service",
                        "AWS Lambda",
                        "AWS Step Functions",
                        "AWS WAF",
                    ]
                },
            ),
            notifications_with_subscribers=[
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        comparison_operator="GREATER_THAN",
                        notification_type="ACTUAL",
                        threshold=80,
                        threshold_type="PERCENTAGE",
                    ),
                    subscribers=[
                        budgets.CfnBudget.SubscriberProperty(
                            address=alarm_topic.topic_arn,
                            subscription_type="SNS",
                        )
                    ],
                )
            ],
        )
        observability_dashboard = cloudwatch.Dashboard(
            self,
            "NovaRuntimeObservabilityDashboard",
            dashboard_name=observability_dashboard_name(
                inputs.deployment_environment
            ),
        )
        api_concurrency_metric = api_function.metric(
            "ConcurrentExecutions",
            statistic="Maximum",
            period=Duration.minutes(5),
        )
        api_saturation_metrics: list[cloudwatch.IMetric] = [
            api_concurrency_metric,
        ]
        if inputs.api_reserved_concurrency is not None:
            api_saturation_metrics.append(
                cloudwatch.MathExpression(
                    expression=(
                        f"100 * concurrent / {inputs.api_reserved_concurrency}"
                    ),
                    label="api_reserved_concurrency_saturation_pct",
                    period=Duration.minutes(5),
                    using_metrics={
                        "concurrent": api_concurrency_metric,
                    },
                )
            )
        observability_dashboard.add_widgets(
            cloudwatch.TextWidget(
                markdown=(
                    "# Nova runtime observability\n"
                    "Baseline coverage for transfer control-plane, export "
                    "workflow, incomplete multipart uploads, and Lambda "
                    "reserved-concurrency saturation. Storage Lens widgets "
                    "remain empty until advanced metrics and CloudWatch "
                    "publishing are enabled for the configured dashboard id."
                ),
                width=24,
                height=5,
            ),
            cloudwatch.GraphWidget(
                title="Transfer control-plane requests",
                width=12,
                left=[
                    cloudwatch.Metric(
                        namespace=metrics_namespace,
                        metric_name="requests_total",
                        dimensions_map={
                            "route": "uploads_initiate",
                            "status": "ok",
                        },
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="uploads_initiate",
                    ),
                    cloudwatch.Metric(
                        namespace=metrics_namespace,
                        metric_name="requests_total",
                        dimensions_map={
                            "route": "uploads_sign_parts",
                            "status": "ok",
                        },
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="uploads_sign_parts",
                    ),
                    cloudwatch.Metric(
                        namespace=metrics_namespace,
                        metric_name="requests_total",
                        dimensions_map={
                            "route": "uploads_complete",
                            "status": "ok",
                        },
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="uploads_complete",
                    ),
                    cloudwatch.Metric(
                        namespace=metrics_namespace,
                        metric_name="requests_total",
                        dimensions_map={
                            "route": "uploads_abort",
                            "status": "ok",
                        },
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="uploads_abort",
                    ),
                ],
            ),
            cloudwatch.GraphWidget(
                title="API throttles and reserved concurrency saturation",
                width=12,
                left=api_saturation_metrics,
                right=[
                    api_function.metric_throttles(period=Duration.minutes(5)),
                    ingress.rest_api.metric_server_error(
                        period=Duration.minutes(5)
                    ),
                ],
            ),
            cloudwatch.GraphWidget(
                title="Export workflow stage age",
                width=12,
                left=[
                    cloudwatch.Metric(
                        namespace=metrics_namespace,
                        metric_name="exports_queued_age_ms",
                        dimensions_map={
                            "source": "export_status_update",
                        },
                        statistic="Average",
                        period=Duration.minutes(5),
                    ),
                    cloudwatch.Metric(
                        namespace=metrics_namespace,
                        metric_name="exports_copying_age_ms",
                        dimensions_map={
                            "source": "export_status_update",
                        },
                        statistic="Average",
                        period=Duration.minutes(5),
                    ),
                    cloudwatch.Metric(
                        namespace=metrics_namespace,
                        metric_name="exports_finalizing_age_ms",
                        dimensions_map={
                            "source": "export_status_update",
                        },
                        statistic="Average",
                        period=Duration.minutes(5),
                    ),
                ],
            ),
            cloudwatch.GraphWidget(
                title="Export workflow health",
                width=12,
                left=[
                    state_machine.metric_failed(period=Duration.minutes(5)),
                    state_machine.metric_timed_out(period=Duration.minutes(5)),
                    *[
                        cloudwatch.Metric(
                            namespace=metrics_namespace,
                            metric_name="exports_status_updates_total",
                            dimensions_map={"status": status},
                            statistic="Sum",
                            period=Duration.minutes(5),
                            label=f"exports_status_updates_total[{status}]",
                        )
                        for status in (
                            "queued",
                            "validating",
                            "copying",
                            "finalizing",
                            "succeeded",
                            "failed",
                            "cancelled",
                        )
                    ],
                ],
            ),
            cloudwatch.GraphWidget(
                title="Export copy worker queue and DLQ",
                width=12,
                left=[
                    export_copy_queue.metric_approximate_number_of_messages_visible(
                        period=Duration.minutes(5)
                    ),
                    export_copy_queue.metric_approximate_age_of_oldest_message(
                        period=Duration.minutes(5)
                    ),
                ],
                right=[
                    export_copy_dlq.metric_approximate_number_of_messages_visible(
                        period=Duration.minutes(5)
                    ),
                    export_copy_worker_fn.metric_throttles(
                        period=Duration.minutes(5)
                    ),
                ],
            ),
            cloudwatch.GraphWidget(
                title="S3 incomplete multipart uploads older than 7 days",
                width=12,
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/S3/Storage-Lens",
                        metric_name="IncompleteMPUStorageBytesOlderThan7Days",
                        dimensions_map=storage_lens_dimensions,
                        statistic="Average",
                        period=Duration.days(1),
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/S3/Storage-Lens",
                        metric_name="IncompleteMPUObjectCountOlderThan7Days",
                        dimensions_map=storage_lens_dimensions,
                        statistic="Average",
                        period=Duration.days(1),
                    ),
                ],
            ),
            cloudwatch.GraphWidget(
                title="S3 incomplete multipart upload footprint",
                width=12,
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/S3/Storage-Lens",
                        metric_name="IncompleteMultipartUploadStorageBytes",
                        dimensions_map=storage_lens_dimensions,
                        statistic="Average",
                        period=Duration.days(1),
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/S3/Storage-Lens",
                        metric_name="IncompleteMultipartUploadObjectCount",
                        dimensions_map=storage_lens_dimensions,
                        statistic="Average",
                        period=Duration.days(1),
                    ),
                ],
            ),
        )
        self._emit_stack_outputs(
            deployment_environment=inputs.deployment_environment,
            public_base_url=ingress.public_base_url,
            state_machine_arn=state_machine.state_machine_arn,
            alarm_topic_arn=alarm_topic.topic_arn,
            api_access_log_group_name=ingress.access_log_group_name,
            exports_table_name=export_table.table_name,
            idempotency_table_name=idempotency_table.table_name,
            upload_sessions_table_name=upload_sessions_table.table_name,
            transfer_usage_table_name=transfer_usage_table.table_name,
            export_copy_parts_table_name=export_copy_parts_table.table_name,
            transfer_policy_appconfig_application_id=(
                transfer_policy_application.ref
            ),
            transfer_policy_appconfig_environment_id=(
                transfer_policy_environment.ref
            ),
            transfer_policy_appconfig_profile_id=transfer_policy_profile.ref,
            observability_dashboard_name=observability_dashboard.dashboard_name,
            storage_lens_configuration_id=storage_lens_configuration_id,
            transfer_spend_budget_name=transfer_budget_name,
            waf_log_group_name=ingress.waf_log_group_name,
        )

    def _emit_stack_outputs(
        self,
        *,
        deployment_environment: str,
        public_base_url: str,
        state_machine_arn: str,
        alarm_topic_arn: str,
        api_access_log_group_name: str,
        exports_table_name: str,
        idempotency_table_name: str,
        upload_sessions_table_name: str,
        transfer_usage_table_name: str,
        export_copy_parts_table_name: str,
        transfer_policy_appconfig_application_id: str,
        transfer_policy_appconfig_environment_id: str,
        transfer_policy_appconfig_profile_id: str,
        observability_dashboard_name: str,
        storage_lens_configuration_id: str,
        transfer_spend_budget_name: str,
        waf_log_group_name: str | None,
    ) -> None:
        """Emit the stable CloudFormation exports for runtime consumers."""
        prefix = export_name_prefix(deployment_environment)
        for logical_id, export_suffix, value in (
            ("ExportNovaPublicBaseUrl", "PublicBaseUrl", public_base_url),
            (
                "ExportNovaExportWorkflowStateMachineArn",
                "ExportWorkflowStateMachineArn",
                state_machine_arn,
            ),
            ("ExportNovaAlarmTopicArn", "AlarmTopicArn", alarm_topic_arn),
            (
                "ExportNovaApiAccessLogGroupName",
                "ApiAccessLogGroupName",
                api_access_log_group_name,
            ),
            (
                "ExportNovaExportsTableName",
                "ExportsTableName",
                exports_table_name,
            ),
            (
                "ExportNovaIdempotencyTableName",
                "IdempotencyTableName",
                idempotency_table_name,
            ),
            (
                "ExportNovaUploadSessionsTableName",
                "UploadSessionsTableName",
                upload_sessions_table_name,
            ),
            (
                "ExportNovaTransferUsageTableName",
                "TransferUsageTableName",
                transfer_usage_table_name,
            ),
            (
                "ExportNovaExportCopyPartsTableName",
                "ExportCopyPartsTableName",
                export_copy_parts_table_name,
            ),
            (
                "ExportNovaTransferPolicyAppConfigApplicationId",
                "TransferPolicyAppConfigApplicationId",
                transfer_policy_appconfig_application_id,
            ),
            (
                "ExportNovaTransferPolicyAppConfigEnvironmentId",
                "TransferPolicyAppConfigEnvironmentId",
                transfer_policy_appconfig_environment_id,
            ),
            (
                "ExportNovaTransferPolicyAppConfigProfileId",
                "TransferPolicyAppConfigProfileId",
                transfer_policy_appconfig_profile_id,
            ),
            (
                "ExportNovaObservabilityDashboardName",
                "ObservabilityDashboardName",
                observability_dashboard_name,
            ),
            (
                "ExportNovaStorageLensConfigurationId",
                "StorageLensConfigurationId",
                storage_lens_configuration_id,
            ),
            (
                "ExportNovaTransferSpendBudgetName",
                "TransferSpendBudgetName",
                transfer_spend_budget_name,
            ),
        ):
            CfnOutput(
                self,
                logical_id,
                value=value,
                export_name=f"{prefix}{export_suffix}",
            )
        if waf_log_group_name is not None:
            CfnOutput(
                self,
                "ExportNovaWafLogGroupName",
                value=waf_log_group_name,
                export_name=f"{prefix}WafLogGroupName",
            )
