# mypy: disable-error-code=import-not-found

"""CDK stack for the canonical Nova runtime."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from .ingress import create_regional_rest_ingress

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
    if deployment_environment in {"prod", "production"}:
        return "prod"
    return deployment_environment


def _default_api_reserved_concurrency(deployment_environment: str) -> int:
    """Return a safe default reserved concurrency for one environment."""
    if deployment_environment in {"prod", "production"}:
        return 25
    return 0


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
    hosted_zone_id: str
    hosted_zone_name: str
    oidc_audience: str
    oidc_issuer: str
    oidc_jwks_url: str
    waf_rate_limit: int

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
            if deployment_environment in {"prod", "production"}:
                raise ValueError(
                    "allowed_origins must be configured for production "
                    "deployments."
                )
            allowed_origins = ["*"]
        raw_reserved_concurrency = scope.node.try_get_context(
            "api_reserved_concurrency"
        )
        if raw_reserved_concurrency is None:
            raw_reserved_concurrency = os.environ.get(
                "API_RESERVED_CONCURRENCY"
            )
        api_reserved_concurrency: int | None
        if raw_reserved_concurrency is None or (
            isinstance(raw_reserved_concurrency, str)
            and not raw_reserved_concurrency.strip()
        ):
            default_reserved_concurrency = _default_api_reserved_concurrency(
                deployment_environment
            )
            api_reserved_concurrency = (
                default_reserved_concurrency
                if default_reserved_concurrency > 0
                else None
            )
        else:
            parsed_reserved_concurrency = int(raw_reserved_concurrency)
            if parsed_reserved_concurrency < 1:
                raise ValueError("api_reserved_concurrency must be >= 1.")
            api_reserved_concurrency = parsed_reserved_concurrency
        return cls(
            allowed_origins=allowed_origins,
            api_reserved_concurrency=api_reserved_concurrency,
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
                )
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

        common_env = {
            "FILE_TRANSFER_BUCKET": file_bucket.bucket_name,
            "FILE_TRANSFER_UPLOAD_PREFIX": "uploads/",
            "FILE_TRANSFER_EXPORT_PREFIX": "exports/",
            "FILE_TRANSFER_TMP_PREFIX": "tmp/",
            "ALLOWED_ORIGINS": json.dumps(inputs.allowed_origins),
            "JOBS_ENABLED": "true",
            "JOBS_REPOSITORY_BACKEND": "dynamodb",
            "JOBS_DYNAMODB_TABLE": export_table.table_name,
            "ACTIVITY_STORE_BACKEND": "dynamodb",
            "ACTIVITY_ROLLUPS_TABLE": activity_table.table_name,
            "OIDC_ISSUER": inputs.oidc_issuer,
            "OIDC_AUDIENCE": inputs.oidc_audience,
            "OIDC_JWKS_URL": inputs.oidc_jwks_url,
        }
        task_env = {
            **common_env,
            "IDEMPOTENCY_ENABLED": "false",
            "JOBS_QUEUE_BACKEND": "memory",
        }
        workflow_fn_props = {
            "architecture": lambda_.Architecture.ARM_64,
            "timeout": Duration.minutes(5),
            "memory_size": 1024,
            "tracing": lambda_.Tracing.ACTIVE,
        }

        validate_fn = lambda_.DockerImageFunction(
            self,
            "ValidateExportFunction",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(REPO_ROOT),
                file="apps/nova_workflows_tasks/Dockerfile",
                cmd=["nova_workflows.handlers.validate_export_handler"],
            ),
            environment=task_env,
            log_group=_runtime_log_group(
                self,
                function_name="ValidateExportFunction",
            ),
            **workflow_fn_props,
        )
        copy_fn = lambda_.DockerImageFunction(
            self,
            "CopyExportFunction",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(REPO_ROOT),
                file="apps/nova_workflows_tasks/Dockerfile",
                cmd=["nova_workflows.handlers.copy_export_handler"],
            ),
            environment=task_env,
            log_group=_runtime_log_group(
                self,
                function_name="CopyExportFunction",
            ),
            **workflow_fn_props,
        )
        finalize_fn = lambda_.DockerImageFunction(
            self,
            "FinalizeExportFunction",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(REPO_ROOT),
                file="apps/nova_workflows_tasks/Dockerfile",
                cmd=["nova_workflows.handlers.finalize_export_handler"],
            ),
            environment=task_env,
            log_group=_runtime_log_group(
                self,
                function_name="FinalizeExportFunction",
            ),
            **workflow_fn_props,
        )
        fail_fn = lambda_.DockerImageFunction(
            self,
            "FailExportFunction",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(REPO_ROOT),
                file="apps/nova_workflows_tasks/Dockerfile",
                cmd=["nova_workflows.handlers.fail_export_handler"],
            ),
            environment=task_env,
            log_group=_runtime_log_group(
                self,
                function_name="FailExportFunction",
            ),
            **workflow_fn_props,
        )

        for function in (validate_fn, copy_fn, finalize_fn, fail_fn):
            file_bucket.grant_read_write(function)
            export_table.grant_read_write_data(function)
            activity_table.grant_read_write_data(function)

        workflow_failure = tasks.LambdaInvoke(
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
        ).next(sfn.Fail(self, "WorkflowFailed"))

        validate_task = tasks.LambdaInvoke(
            self,
            "ValidateExport",
            lambda_function=validate_fn,
            payload_response_only=True,
        )
        copy_task = tasks.LambdaInvoke(
            self,
            "CopyExport",
            lambda_function=copy_fn,
            payload_response_only=True,
        )
        finalize_task = tasks.LambdaInvoke(
            self,
            "FinalizeExport",
            lambda_function=finalize_fn,
            payload_response_only=True,
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
                "JOBS_QUEUE_BACKEND": "stepfunctions",
                "JOBS_STEP_FUNCTIONS_STATE_MACHINE_ARN": (
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
            waf_rate_limit=inputs.waf_rate_limit,
        )

        cloudwatch.Alarm(
            self,
            "ApiLambdaErrorsAlarm",
            metric=api_function.metric_errors(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when the API Lambda records errors.",
        )
        cloudwatch.Alarm(
            self,
            "ApiLambdaLatencyAlarm",
            metric=api_function.metric_duration(
                period=Duration.minutes(5),
                statistic="p95",
            ),
            threshold=5000,
            evaluation_periods=1,
            alarm_description="Alarm when API Lambda p95 duration exceeds 5s.",
        )
        cloudwatch.Alarm(
            self,
            "ExportWorkflowFailuresAlarm",
            metric=state_machine.metric_failed(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when export workflow executions fail.",
        )
        cloudwatch.Alarm(
            self,
            "ExportWorkflowTimeoutsAlarm",
            metric=state_machine.metric_timed_out(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when export workflow executions time out.",
        )
        cloudwatch.Alarm(
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
        )

        self.export_value(
            ingress.public_base_url,
            name="NovaPublicBaseUrl",
        )
        self.export_value(
            state_machine.state_machine_arn,
            name="NovaExportWorkflowStateMachineArn",
        )
        self.export_value(export_table.table_name, name="NovaExportsTableName")
        self.export_value(
            idempotency_table.table_name,
            name="NovaIdempotencyTableName",
        )
