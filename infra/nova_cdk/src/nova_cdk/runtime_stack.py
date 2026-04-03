# mypy: disable-error-code=import-not-found

"""CDK stack for the canonical Nova runtime."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_route53 as route53,
    aws_s3 as s3,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
)
from constructs import Construct

from .concurrency import (
    default_api_reserved_concurrency,
    default_workflow_reserved_concurrency,
    is_production_environment,
)
from .iam import (
    grant_copy_export_permissions,
    grant_export_status_permissions,
)
from .ingress import create_regional_rest_ingress
from .observability import add_alarm_actions, create_alarm_topic

REPO_ROOT = Path(__file__).resolve().parents[4]


def _parse_allowed_origins(raw: object | None) -> list[str]:
    """Normalize configured CORS origins into a non-empty string list."""
    if raw is None:
        return []
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return []
        if value.startswith("["):
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise TypeError(
                    "allowed_origins JSON input must decode to a list."
                )
            return _parse_allowed_origins(parsed)
        return [
            origin
            for origin in (item.strip() for item in value.split(","))
            if origin
        ]
    if isinstance(raw, (list, tuple)):
        return [str(origin).strip() for origin in raw if str(origin).strip()]
    raise TypeError("allowed_origins must be a string or a list of strings")


def _required_context_or_env_value(
    scope: Construct,
    *,
    env_var: str,
    key: str,
) -> str:
    """Return one required non-blank context or environment value."""
    raw = scope.node.try_get_context(key)
    if not isinstance(raw, str):
        raw = os.environ.get(env_var)
    if isinstance(raw, str):
        value = raw.strip()
        if value:
            return value
    raise ValueError(f"Missing required value for {key}.")


def _numeric_context_or_env_value(
    scope: Construct,
    *,
    env_var: str,
    key: str,
    default: int | float,
    allow_float: bool = False,
    minimum: int | float = 1,
) -> int | float:
    """Return one validated numeric context or environment value."""
    raw = scope.node.try_get_context(key)
    if raw is None:
        raw = os.environ.get(env_var)
    if raw is None:
        return default
    if isinstance(raw, str):
        value_text = raw.strip()
        if not value_text:
            return default
        value: int | float = (
            float(value_text) if allow_float else int(value_text)
        )
    elif isinstance(raw, (int, float)):
        value = float(raw) if allow_float else int(raw)
    else:
        raise TypeError(f"{key} must be numeric.")
    if value < minimum:
        raise ValueError(f"{key} must be >= {minimum}.")
    return value


def _sha256_context_or_env_value(
    scope: Construct,
    *,
    env_var: str,
    key: str,
) -> str:
    """Return one required lowercase SHA-256 digest from context or env."""
    value = _required_context_or_env_value(
        scope,
        env_var=env_var,
        key=key,
    )
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{key} must be a lowercase 64-character SHA-256.")
    return value


def _stage_name_for_environment(deployment_environment: str) -> str:
    """Normalize environment values into a stable API Gateway stage name."""
    if is_production_environment(deployment_environment):
        return "prod"
    return deployment_environment


def _export_name_prefix(deployment_environment: str) -> str:
    """Return the environment-scoped CloudFormation export prefix."""
    if is_production_environment(deployment_environment):
        return "NovaProd"
    if deployment_environment == "dev":
        return "NovaDev"
    normalized = "".join(
        part.capitalize()
        for part in deployment_environment.replace("_", "-").split("-")
        if part
    )
    return f"Nova{normalized or 'Env'}"


def _optional_context_or_env_value(
    scope: Construct,
    *,
    env_var: str,
    key: str,
) -> object | None:
    """Return one optional context or environment value."""
    raw: object | None = scope.node.try_get_context(key)
    if raw is None:
        raw = os.environ.get(env_var)
    return raw


def _parse_bool_flag(
    raw: object,
    *,
    key: str,
) -> bool:
    """Return one normalized boolean flag value."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"{key} must be a boolean value.")


def _reserved_concurrency_enabled(
    scope: Construct,
    *,
    deployment_environment: str,
) -> bool:
    """Return whether Lambda reserved concurrency should be configured."""
    raw = _optional_context_or_env_value(
        scope,
        env_var="ENABLE_RESERVED_CONCURRENCY",
        key="enable_reserved_concurrency",
    )
    enabled = (
        True
        if raw is None
        else _parse_bool_flag(raw, key="enable_reserved_concurrency")
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
    raw = scope.node.try_get_context(key)
    if raw is None:
        raw = os.environ.get(env_var)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return default
    value = int(raw)
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
    raw = _optional_context_or_env_value(
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
        allowed_origins = _parse_allowed_origins(
            scope.node.try_get_context("allowed_origins")
            or os.environ.get("STACK_ALLOWED_ORIGINS")
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
        enable_waf_raw = _optional_context_or_env_value(
            scope,
            env_var="ENABLE_WAF",
            key="enable_waf",
        )
        enable_waf = (
            is_production_environment(deployment_environment)
            if enable_waf_raw is None
            else _parse_bool_flag(enable_waf_raw, key="enable_waf")
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
                _numeric_context_or_env_value(
                    scope,
                    env_var="API_STAGE_THROTTLING_BURST_LIMIT",
                    key="api_stage_throttling_burst_limit",
                    default=100,
                )
            ),
            api_stage_throttling_rate_limit=float(
                _numeric_context_or_env_value(
                    scope,
                    env_var="API_STAGE_THROTTLING_RATE_LIMIT",
                    key="api_stage_throttling_rate_limit",
                    default=50,
                    allow_float=True,
                )
            ),
            api_domain_name=_required_context_or_env_value(
                scope,
                env_var="API_DOMAIN_NAME",
                key="api_domain_name",
            ),
            certificate_arn=_required_context_or_env_value(
                scope,
                env_var="CERTIFICATE_ARN",
                key="certificate_arn",
            ),
            deployment_environment=deployment_environment,
            enable_waf=enable_waf,
            enable_reserved_concurrency=enable_reserved_concurrency,
            hosted_zone_id=_required_context_or_env_value(
                scope,
                env_var="HOSTED_ZONE_ID",
                key="hosted_zone_id",
            ),
            hosted_zone_name=_required_context_or_env_value(
                scope,
                env_var="HOSTED_ZONE_NAME",
                key="hosted_zone_name",
            ),
            oidc_audience=_required_context_or_env_value(
                scope,
                env_var="JWT_AUDIENCE",
                key="jwt_audience",
            ),
            oidc_issuer=_required_context_or_env_value(
                scope,
                env_var="JWT_ISSUER",
                key="jwt_issuer",
            ),
            oidc_jwks_url=_required_context_or_env_value(
                scope,
                env_var="JWT_JWKS_URL",
                key="jwt_jwks_url",
            ),
            waf_rate_limit=int(
                _numeric_context_or_env_value(
                    scope,
                    env_var="WAF_RATE_LIMIT",
                    key="waf_rate_limit",
                    default=2000,
                    minimum=100,
                )
            ),
            waf_write_rate_limit=int(
                _numeric_context_or_env_value(
                    scope,
                    env_var="WAF_WRITE_RATE_LIMIT",
                    key="waf_write_rate_limit",
                    default=500,
                    minimum=100,
                )
            ),
            workflow_lambda_artifact_bucket=_required_context_or_env_value(
                scope,
                env_var="WORKFLOW_LAMBDA_ARTIFACT_BUCKET",
                key="workflow_lambda_artifact_bucket",
            ),
            workflow_lambda_artifact_key=_required_context_or_env_value(
                scope,
                env_var="WORKFLOW_LAMBDA_ARTIFACT_KEY",
                key="workflow_lambda_artifact_key",
            ),
            workflow_lambda_artifact_sha256=_sha256_context_or_env_value(
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

        file_bucket = s3.Bucket(
            self,
            "FileTransferBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
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

        workflow_common_env = {
            "FILE_TRANSFER_BUCKET": file_bucket.bucket_name,
            "FILE_TRANSFER_UPLOAD_PREFIX": "uploads/",
            "FILE_TRANSFER_EXPORT_PREFIX": "exports/",
            "FILE_TRANSFER_TMP_PREFIX": "tmp/",
            "EXPORTS_ENABLED": "true",
            "EXPORTS_DYNAMODB_TABLE": export_table.table_name,
        }
        common_env = {
            **workflow_common_env,
            "ALLOWED_ORIGINS": json.dumps(inputs.allowed_origins),
            "ACTIVITY_STORE_BACKEND": "dynamodb",
            "ACTIVITY_ROLLUPS_TABLE": activity_table.table_name,
            "OIDC_ISSUER": inputs.oidc_issuer,
            "OIDC_AUDIENCE": inputs.oidc_audience,
            "OIDC_JWKS_URL": inputs.oidc_jwks_url,
        }
        task_env = {
            **workflow_common_env,
            "IDEMPOTENCY_ENABLED": "false",
        }
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

        validate_fn = lambda_.Function(
            self,
            "ValidateExportFunction",
            handler="nova_workflows.handlers.validate_export_handler",
            environment=task_env,
            log_group=_runtime_log_group(
                self,
                function_name="ValidateExportFunction",
            ),
            **workflow_fn_props,
        )
        finalize_fn = lambda_.Function(
            self,
            "FinalizeExportFunction",
            handler="nova_workflows.handlers.finalize_export_handler",
            environment=task_env,
            log_group=_runtime_log_group(
                self,
                function_name="FinalizeExportFunction",
            ),
            **workflow_fn_props,
        )
        fail_fn = lambda_.Function(
            self,
            "FailExportFunction",
            handler="nova_workflows.handlers.fail_export_handler",
            environment=task_env,
            log_group=_runtime_log_group(
                self,
                function_name="FailExportFunction",
            ),
            **workflow_fn_props,
        )
        copy_fn = lambda_.Function(
            self,
            "CopyExportFunction",
            handler="nova_workflows.handlers.copy_export_handler",
            environment=task_env,
            log_group=_runtime_log_group(
                self,
                function_name="CopyExportFunction",
            ),
            **workflow_fn_props,
        )

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
        grant_copy_export_permissions(
            function=copy_fn,
            export_table=export_table,
            file_bucket=file_bucket,
            export_prefix="exports/",
            upload_prefix="uploads/",
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
        copy_task = tasks.LambdaInvoke(
            self,
            "CopyExport",
            lambda_function=copy_fn,
            payload_response_only=True,
            retry_on_service_exceptions=False,
        )
        finalize_task = tasks.LambdaInvoke(
            self,
            "FinalizeExport",
            lambda_function=finalize_fn,
            payload_response_only=True,
            retry_on_service_exceptions=False,
        )

        for task in (
            validate_task,
            copy_task,
            finalize_task,
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
        for task in (validate_task, copy_task, finalize_task):
            task.add_catch(workflow_failure, result_path="$.workflow_error")

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
                validate_task.next(copy_task)
                .next(finalize_task)
                .next(sfn.Succeed(self, "ExportCompleted"))
            ),
            logs=sfn.LogOptions(
                destination=state_machine_log_group,
                level=sfn.LogLevel.ALL,
            ),
            tracing_enabled=True,
            timeout=Duration.minutes(15),
        )

        api_lambda_artifact_bucket_name = _required_context_or_env_value(
            self,
            env_var="API_LAMBDA_ARTIFACT_BUCKET",
            key="api_lambda_artifact_bucket",
        )
        api_lambda_artifact_key = _required_context_or_env_value(
            self,
            env_var="API_LAMBDA_ARTIFACT_KEY",
            key="api_lambda_artifact_key",
        )
        api_lambda_artifact_sha256 = _sha256_context_or_env_value(
            self,
            env_var="API_LAMBDA_ARTIFACT_SHA256",
            key="api_lambda_artifact_sha256",
        )
        api_lambda_artifact_bucket = s3.Bucket.from_bucket_name(
            self,
            "ApiLambdaArtifactBucket",
            api_lambda_artifact_bucket_name,
        )

        api_function_kwargs: dict[str, Any] = {
            "runtime": lambda_.Runtime.PYTHON_3_13,
            "handler": "nova_file_api.lambda_handler.handler",
            "code": lambda_.Code.from_bucket(
                api_lambda_artifact_bucket,
                api_lambda_artifact_key,
            ),
            "architecture": lambda_.Architecture.ARM_64,
            "memory_size": 2048,
            "timeout": Duration.seconds(29),
            "tracing": lambda_.Tracing.ACTIVE,
            "environment": {
                **common_env,
                "IDEMPOTENCY_ENABLED": "true",
                "IDEMPOTENCY_DYNAMODB_TABLE": idempotency_table.table_name,
                "EXPORT_WORKFLOW_STATE_MACHINE_ARN": (
                    state_machine.state_machine_arn
                ),
                "API_RELEASE_ARTIFACT_SHA256": api_lambda_artifact_sha256,
            },
            "log_group": _runtime_log_group(
                self,
                function_name="NovaApiFunction",
            ),
        }
        if inputs.api_reserved_concurrency is not None:
            api_function_kwargs["reserved_concurrent_executions"] = (
                inputs.api_reserved_concurrency
            )

        api_function = lambda_.Function(
            self,
            "NovaApiFunction",
            **api_function_kwargs,
        )
        file_bucket.grant_read_write(api_function)
        export_table.grant_read_write_data(api_function)
        activity_table.grant_read_write_data(api_function)
        idempotency_table.grant_read_write_data(api_function)
        state_machine.grant_start_execution(api_function)
        api_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["states:DescribeStateMachine"],
                resources=[state_machine.state_machine_arn],
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
            stage_name=_stage_name_for_environment(
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
        api_lambda_errors_alarm = cloudwatch.Alarm(
            self,
            "ApiLambdaErrorsAlarm",
            metric=api_function.metric_errors(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when the API Lambda records errors.",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        api_lambda_throttles_alarm = cloudwatch.Alarm(
            self,
            "ApiLambdaThrottlesAlarm",
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
            metric=cloudwatch.MathExpression(
                expression="validate + copy + finalize + fail",
                period=Duration.minutes(5),
                using_metrics={
                    "validate": validate_fn.metric_throttles(
                        period=Duration.minutes(5)
                    ),
                    "copy": copy_fn.metric_throttles(
                        period=Duration.minutes(5)
                    ),
                    "finalize": finalize_fn.metric_throttles(
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
            metric=state_machine.metric_failed(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when export workflow executions fail.",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        export_workflow_timeouts_alarm = cloudwatch.Alarm(
            self,
            "ExportWorkflowTimeoutsAlarm",
            metric=state_machine.metric_timed_out(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when export workflow executions time out.",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        exports_table_throttles_alarm = cloudwatch.Alarm(
            self,
            "ExportsTableThrottlesAlarm",
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
        add_alarm_actions(
            alarms=[
                api_gateway_5xx_alarm,
                api_latency_alarm,
                api_lambda_errors_alarm,
                api_lambda_throttles_alarm,
                export_workflow_failures_alarm,
                export_workflow_timeouts_alarm,
                exports_table_throttles_alarm,
                workflow_task_throttles_alarm,
            ],
            topic=alarm_topic,
        )
        export_prefix = _export_name_prefix(inputs.deployment_environment)
        for logical_id, export_suffix, value in (
            (
                "ExportNovaPublicBaseUrl",
                "PublicBaseUrl",
                ingress.public_base_url,
            ),
            (
                "ExportNovaExportWorkflowStateMachineArn",
                "ExportWorkflowStateMachineArn",
                state_machine.state_machine_arn,
            ),
            (
                "ExportNovaAlarmTopicArn",
                "AlarmTopicArn",
                alarm_topic.topic_arn,
            ),
            (
                "ExportNovaApiAccessLogGroupName",
                "ApiAccessLogGroupName",
                ingress.access_log_group_name,
            ),
            (
                "ExportNovaExportsTableName",
                "ExportsTableName",
                export_table.table_name,
            ),
            (
                "ExportNovaIdempotencyTableName",
                "IdempotencyTableName",
                idempotency_table.table_name,
            ),
        ):
            CfnOutput(
                self,
                logical_id,
                value=value,
                export_name=f"{export_prefix}{export_suffix}",
            )
        if ingress.waf_log_group_name is not None:
            CfnOutput(
                self,
                "ExportNovaWafLogGroupName",
                value=ingress.waf_log_group_name,
                export_name=f"{export_prefix}WafLogGroupName",
            )
