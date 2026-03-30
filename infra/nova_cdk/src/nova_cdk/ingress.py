# mypy: disable-error-code=import-not-found

"""Regional REST API ingress for the canonical Nova runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass

from aws_cdk import Aws
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct


@dataclass(frozen=True)
class IngressResources:
    """Describe the public ingress resources exposed by the runtime stack."""

    public_base_url: str
    rest_api: apigw.RestApi
    stage_name: str


def _build_access_log_format() -> apigw.AccessLogFormat:
    """Return the canonical JSON access-log format for REST API stages."""
    return apigw.AccessLogFormat.custom(
        json.dumps(
            {
                "requestId": "$context.requestId",
                "ip": "$context.identity.sourceIp",
                "requestTime": "$context.requestTime",
                "httpMethod": "$context.httpMethod",
                "resourcePath": "$context.resourcePath",
                "status": "$context.status",
                "responseLength": "$context.responseLength",
            },
            separators=(",", ":"),
        )
    )


def _managed_web_acl_rules(
    *,
    rate_limit: int,
) -> list[wafv2.CfnWebACL.RuleProperty]:
    """Return the baseline regional WAF rules for the public REST ingress."""
    return [
        wafv2.CfnWebACL.RuleProperty(
            name="AWSManagedCommonRuleSet",
            priority=1,
            override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                    vendor_name="AWS",
                    name="AWSManagedRulesCommonRuleSet",
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="nova-rest-api-managed-common",
                sampled_requests_enabled=True,
            ),
        ),
        wafv2.CfnWebACL.RuleProperty(
            name="NovaRateLimitByIp",
            priority=2,
            action=wafv2.CfnWebACL.RuleActionProperty(block={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                    aggregate_key_type="IP",
                    evaluation_window_sec=300,
                    limit=rate_limit,
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="nova-rest-api-rate-limit",
                sampled_requests_enabled=True,
            ),
        ),
    ]


def create_regional_rest_ingress(
    scope: Construct,
    *,
    api_domain_name: str,
    api_handler: lambda_.IFunction,
    certificate_arn: str,
    stage_name: str,
    throttling_burst_limit: int,
    throttling_rate_limit: float,
    waf_rate_limit: int,
) -> IngressResources:
    """Create the canonical public REST ingress for the Nova runtime."""
    access_log_group = logs.LogGroup(
        scope,
        "NovaApiAccessLogs",
        retention=logs.RetentionDays.ONE_MONTH,
    )
    integration = apigw.LambdaIntegration(api_handler, proxy=True)
    rest_api = apigw.RestApi(
        scope,
        "NovaRestApi",
        cloud_watch_role=True,
        disable_execute_api_endpoint=True,
        endpoint_types=[apigw.EndpointType.REGIONAL],
        deploy_options=apigw.StageOptions(
            access_log_destination=apigw.LogGroupLogDestination(
                access_log_group
            ),
            access_log_format=_build_access_log_format(),
            data_trace_enabled=False,
            logging_level=apigw.MethodLoggingLevel.ERROR,
            metrics_enabled=True,
            stage_name=stage_name,
            throttling_burst_limit=throttling_burst_limit,
            throttling_rate_limit=throttling_rate_limit,
            tracing_enabled=True,
        ),
    )
    rest_api.root.add_method("ANY", integration)
    rest_api.root.add_proxy(any_method=True, default_integration=integration)

    certificate = acm.Certificate.from_certificate_arn(
        scope,
        "NovaApiCertificate",
        certificate_arn,
    )
    rest_api.add_domain_name(
        "NovaCustomDomain",
        certificate=certificate,
        domain_name=api_domain_name,
        endpoint_type=apigw.EndpointType.REGIONAL,
        security_policy=apigw.SecurityPolicy.TLS_1_2,
    )

    web_acl = wafv2.CfnWebACL(
        scope,
        "NovaRestApiWebAcl",
        default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
        rules=_managed_web_acl_rules(rate_limit=waf_rate_limit),
        scope="REGIONAL",
        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
            cloud_watch_metrics_enabled=True,
            metric_name="nova-rest-api-waf",
            sampled_requests_enabled=True,
        ),
    )
    wafv2.CfnWebACLAssociation(
        scope,
        "NovaRestApiWebAclAssociation",
        resource_arn=(
            f"arn:{Aws.PARTITION}:apigateway:{Aws.REGION}::/restapis/"
            f"{rest_api.rest_api_id}/stages/{stage_name}"
        ),
        web_acl_arn=web_acl.attr_arn,
    )

    return IngressResources(
        public_base_url=f"https://{api_domain_name}",
        rest_api=rest_api,
        stage_name=stage_name,
    )
