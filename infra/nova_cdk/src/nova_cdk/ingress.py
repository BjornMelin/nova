# mypy: disable-error-code=import-not-found

"""Regional REST API ingress for the canonical Nova runtime."""

from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import (
    Aws,
    aws_apigateway as apigw,
    aws_certificatemanager as acm,
    aws_lambda as lambda_,
    aws_route53 as route53,
    aws_route53_targets as route53_targets,
    aws_wafv2 as wafv2,
)
from constructs import Construct

from .observability import (
    build_api_access_log_format,
    create_api_access_log_group,
    create_waf_log_group,
)


@dataclass(frozen=True)
class IngressResources:
    """Describe the public ingress resources exposed by the runtime stack."""

    access_log_group_name: str
    public_base_url: str
    rest_api: apigw.RestApi
    stage_name: str
    waf_log_group_name: str
    web_acl_arn: str


def _managed_web_acl_rules(
    *,
    write_rate_limit: int,
    rate_limit: int,
) -> list[wafv2.CfnWebACL.RuleProperty]:
    """Return the baseline regional WAF rules for the public REST ingress."""
    return [
        wafv2.CfnWebACL.RuleProperty(
            name="AWSManagedRulesAmazonIpReputationList",
            priority=1,
            override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                    vendor_name="AWS",
                    name="AWSManagedRulesAmazonIpReputationList",
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="nova-rest-api-ip-reputation",
                sampled_requests_enabled=True,
            ),
        ),
        wafv2.CfnWebACL.RuleProperty(
            name="AWSManagedRulesCommonRuleSet",
            priority=2,
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
            name="AWSManagedRulesKnownBadInputsRuleSet",
            priority=3,
            override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                    vendor_name="AWS",
                    name="AWSManagedRulesKnownBadInputsRuleSet",
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="nova-rest-api-known-bad-inputs",
                sampled_requests_enabled=True,
            ),
        ),
        wafv2.CfnWebACL.RuleProperty(
            name="NovaWritePathRateLimitByIp",
            priority=10,
            action=wafv2.CfnWebACL.RuleActionProperty(block={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                    aggregate_key_type="IP",
                    evaluation_window_sec=300,
                    limit=write_rate_limit,
                    scope_down_statement=wafv2.CfnWebACL.StatementProperty(
                        regex_match_statement=wafv2.CfnWebACL.RegexMatchStatementProperty(
                            field_to_match=wafv2.CfnWebACL.FieldToMatchProperty(
                                uri_path={}
                            ),
                            regex_string=(
                                "^/v1/(exports($|/.*)|transfers/uploads($|/.*))"
                            ),
                            text_transformations=[
                                wafv2.CfnWebACL.TextTransformationProperty(
                                    priority=0,
                                    type="NONE",
                                )
                            ],
                        )
                    ),
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="nova-rest-api-write-path-rate-limit",
                sampled_requests_enabled=True,
            ),
        ),
        wafv2.CfnWebACL.RuleProperty(
            name="NovaRateLimitByIp",
            priority=11,
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
    hosted_zone: route53.IHostedZone,
    stage_name: str,
    throttling_burst_limit: int,
    throttling_rate_limit: float,
    waf_rate_limit: int,
    waf_write_rate_limit: int,
) -> IngressResources:
    """Create the canonical public REST ingress for the Nova runtime."""
    access_log_group = create_api_access_log_group(
        scope,
        stage_name=stage_name,
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
                access_log_group.log_group
            ),
            access_log_format=build_api_access_log_format(),
            data_trace_enabled=False,
            logging_level=apigw.MethodLoggingLevel.ERROR,
            metrics_enabled=True,
            stage_name=stage_name,
            throttling_burst_limit=throttling_burst_limit,
            throttling_rate_limit=throttling_rate_limit,
            tracing_enabled=True,
        ),
    )
    rest_api.deployment_stage.node.add_dependency(access_log_group.dependency)
    rest_api.root.add_method("ANY", integration)
    rest_api.root.add_proxy(any_method=True, default_integration=integration)

    certificate = acm.Certificate.from_certificate_arn(
        scope,
        "NovaApiCertificate",
        certificate_arn,
    )
    custom_domain = rest_api.add_domain_name(
        "NovaCustomDomain",
        certificate=certificate,
        domain_name=api_domain_name,
        endpoint_type=apigw.EndpointType.REGIONAL,
        security_policy=apigw.SecurityPolicy.TLS_1_2,
    )
    route53.ARecord(
        scope,
        "NovaApiAliasRecord",
        zone=hosted_zone,
        record_name=api_domain_name,
        target=route53.RecordTarget.from_alias(
            route53_targets.ApiGatewayDomain(custom_domain)
        ),
    )
    route53.AaaaRecord(
        scope,
        "NovaApiAliasRecordIpv6",
        zone=hosted_zone,
        record_name=api_domain_name,
        target=route53.RecordTarget.from_alias(
            route53_targets.ApiGatewayDomain(custom_domain)
        ),
    )

    web_acl = wafv2.CfnWebACL(
        scope,
        "NovaRestApiWebAcl",
        default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
        rules=_managed_web_acl_rules(
            rate_limit=waf_rate_limit,
            write_rate_limit=waf_write_rate_limit,
        ),
        scope="REGIONAL",
        visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
            cloud_watch_metrics_enabled=True,
            metric_name="nova-rest-api-waf",
            sampled_requests_enabled=True,
        ),
    )
    waf_log_group = create_waf_log_group(scope, stage_name=stage_name)
    waf_logging = wafv2.CfnLoggingConfiguration(
        scope,
        "NovaRestApiWebAclLogging",
        log_destination_configs=[waf_log_group.log_group.log_group_arn],
        resource_arn=web_acl.attr_arn,
    )
    waf_logging.add_property_override(
        "LoggingFilter",
        {
            "DefaultBehavior": "DROP",
            "Filters": [
                {
                    "Behavior": "KEEP",
                    "Conditions": [
                        {"ActionCondition": {"Action": "BLOCK"}},
                        {"ActionCondition": {"Action": "COUNT"}},
                    ],
                    "Requirement": "MEETS_ANY",
                }
            ],
        },
    )
    waf_logging.add_property_override(
        "RedactedFields",
        [
            {"SingleHeader": {"Name": "authorization"}},
            {"SingleHeader": {"Name": "cookie"}},
        ],
    )
    waf_logging.node.add_dependency(web_acl)
    waf_logging.node.add_dependency(waf_log_group.dependency)
    web_acl_association = wafv2.CfnWebACLAssociation(
        scope,
        "NovaRestApiWebAclAssociation",
        resource_arn=(
            f"arn:{Aws.PARTITION}:apigateway:{Aws.REGION}::/restapis/"
            f"{rest_api.rest_api_id}/stages/{stage_name}"
        ),
        web_acl_arn=web_acl.attr_arn,
    )
    web_acl_association.node.add_dependency(rest_api.deployment_stage)

    return IngressResources(
        access_log_group_name=access_log_group.log_group.log_group_name,
        public_base_url=f"https://{api_domain_name}",
        rest_api=rest_api,
        stage_name=stage_name,
        waf_log_group_name=waf_log_group.log_group.log_group_name,
        web_acl_arn=web_acl.attr_arn,
    )
