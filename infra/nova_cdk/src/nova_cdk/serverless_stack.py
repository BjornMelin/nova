"""CDK stack for the canonical Nova serverless runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_authorizers as apigwv2_authorizers
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct

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
            try:
                parsed = json.loads(value)
            except ValueError:
                parsed = value
            else:
                raw = parsed
                if not isinstance(raw, list):
                    raise TypeError(
                        "allowed_origins must decode to a JSON list when "
                        "supplied as JSON"
                    )
        else:
            return [
                origin
                for origin in (item.strip() for item in value.split(","))
                if origin
            ]
    if isinstance(raw, (list, tuple)):
        parsed_origins = [
            str(origin).strip() for origin in raw if str(origin).strip()
        ]
        if parsed_origins:
            return parsed_origins
        return []
    raise TypeError("allowed_origins must be a string or a list of strings")


def _required_context_value(
    scope: Construct,
    *,
    key: str,
) -> str:
    """Return one required non-blank CDK context value."""
    value = scope.node.try_get_context(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(
        f"Missing required CDK context value: {key}. "
        "Pass -c jwt_issuer=... -c jwt_audience=... -c jwt_jwks_url=..."
    )


class NovaServerlessStack(Stack):
    """Provision the canonical Nova serverless platform."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs: Any,
    ) -> None:
        """Initialize the serverless stack and all primary runtime resources."""
        super().__init__(scope, construct_id, **kwargs)

        export_table = dynamodb.Table(
            self,
            "ExportsTable",
            partition_key=dynamodb.Attribute(
                name="export_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
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
            point_in_time_recovery=True,
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
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        deployment_environment = (
            str(
                self.node.try_get_context("environment")
                or os.environ.get("ENVIRONMENT")
                or "dev"
            )
            .strip()
            .lower()
        )
        allowed_origins = _parse_allowed_origins(
            self.node.try_get_context("allowed_origins")
            or os.environ.get("STACK_ALLOWED_ORIGINS")
        )
        if not allowed_origins:
            if deployment_environment in {"prod", "production"}:
                raise ValueError(
                    "allowed_origins must be configured for production "
                    "deployments"
                )
            allowed_origins = ["*"]
        oidc_issuer = _required_context_value(self, key="jwt_issuer")
        oidc_audience = _required_context_value(self, key="jwt_audience")
        oidc_jwks_url = _required_context_value(self, key="jwt_jwks_url")

        file_bucket = s3.Bucket(
            self,
            "FileTransferBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
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

        common_env = {
            "FILE_TRANSFER_BUCKET": file_bucket.bucket_name,
            "FILE_TRANSFER_UPLOAD_PREFIX": "uploads/",
            "FILE_TRANSFER_EXPORT_PREFIX": "exports/",
            "FILE_TRANSFER_TMP_PREFIX": "tmp/",
            "JOBS_ENABLED": "true",
            "JOBS_REPOSITORY_BACKEND": "dynamodb",
            "JOBS_DYNAMODB_TABLE": export_table.table_name,
            "ACTIVITY_STORE_BACKEND": "dynamodb",
            "ACTIVITY_ROLLUPS_TABLE": activity_table.table_name,
            "OIDC_ISSUER": oidc_issuer,
            "OIDC_AUDIENCE": oidc_audience,
            "OIDC_JWKS_URL": oidc_jwks_url,
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
            log_retention=logs.RetentionDays.ONE_MONTH,
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
            log_retention=logs.RetentionDays.ONE_MONTH,
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
            log_retention=logs.RetentionDays.ONE_MONTH,
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
            log_retention=logs.RetentionDays.ONE_MONTH,
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

        api_function = lambda_.DockerImageFunction(
            self,
            "NovaApiFunction",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(REPO_ROOT),
                file="apps/nova_file_api_service/Dockerfile",
            ),
            architecture=lambda_.Architecture.ARM_64,
            memory_size=2048,
            timeout=Duration.seconds(29),
            tracing=lambda_.Tracing.ACTIVE,
            environment={
                **common_env,
                "IDEMPOTENCY_ENABLED": "true",
                "IDEMPOTENCY_DYNAMODB_TABLE": idempotency_table.table_name,
                "JOBS_QUEUE_BACKEND": "stepfunctions",
                "JOBS_STEP_FUNCTIONS_STATE_MACHINE_ARN": (
                    state_machine.state_machine_arn
                ),
            },
            log_retention=logs.RetentionDays.ONE_MONTH,
        )
        file_bucket.grant_read_write(api_function)
        export_table.grant_read_write_data(api_function)
        activity_table.grant_read_write_data(api_function)
        idempotency_table.grant_read_write_data(api_function)
        state_machine.grant_start_execution(api_function)

        integration = apigwv2_integrations.HttpLambdaIntegration(
            "NovaApiIntegration",
            api_function,
        )
        http_api = apigwv2.HttpApi(
            self,
            "NovaHttpApi",
            create_default_stage=True,
        )

        authorizer = apigwv2_authorizers.HttpJwtAuthorizer(
            "NovaJwtAuthorizer",
            oidc_issuer,
            jwt_audience=[oidc_audience],
        )
        http_api.add_routes(
            path="/v1/health/live",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )
        http_api.add_routes(
            path="/v1/health/ready",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )
        http_api.add_routes(
            path="/v1/{proxy+}",
            methods=[apigwv2.HttpMethod.ANY],
            integration=integration,
            authorizer=authorizer,
        )
        http_api.add_routes(
            path="/v1",
            methods=[apigwv2.HttpMethod.ANY],
            integration=integration,
            authorizer=authorizer,
        )
        http_api.add_routes(
            path="/",
            methods=[apigwv2.HttpMethod.ANY],
            integration=integration,
        )
        http_api.add_routes(
            path="/metrics/summary",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )

        web_acl = wafv2.CfnWebACL(
            self,
            "NovaCloudFrontWebAcl",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            scope="CLOUDFRONT",
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="nova-cloudfront-waf",
                sampled_requests_enabled=True,
            ),
            rules=[
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedCommonRuleSet",
                    priority=1,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(
                        none={}
                    ),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesCommonRuleSet",
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="nova-managed-common",
                        sampled_requests_enabled=True,
                    ),
                )
            ],
        )

        stack_region = self.region
        api_origin = origins.HttpOrigin(
            f"{http_api.api_id}.execute-api.{stack_region}.{Stack.of(self).url_suffix}",
        )
        distribution = cloudfront.Distribution(
            self,
            "NovaDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=api_origin,
                viewer_protocol_policy=(
                    cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
                ),
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=(
                    cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER
                ),
            ),
            web_acl_id=web_acl.attr_arn,
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
            metric=export_table.metric_throttled_requests(
                period=Duration.minutes(5)
            ),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Alarm when export table requests throttle.",
        )

        self.export_value(http_api.api_endpoint, name="NovaHttpApiEndpoint")
        self.export_value(
            distribution.domain_name,
            name="NovaDistributionDomainName",
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
