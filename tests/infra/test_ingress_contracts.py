# mypy: disable-error-code=import-not-found

"""Contract tests for the canonical Nova ingress."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from .helpers import load_repo_package_module, read_repo_file

_RUNTIME_STACK_MODULE = load_repo_package_module(
    "nova_cdk.runtime_stack",
    "infra/nova_cdk/src",
)
NovaRuntimeStack = _RUNTIME_STACK_MODULE.NovaRuntimeStack


def _context_for_region(region: str) -> dict[str, str]:
    """Return the minimum valid ingress context for one region."""
    return {
        "api_domain_name": "api.dev.example.com",
        "certificate_arn": (
            f"arn:aws:acm:{region}:111111111111:"
            "certificate/12345678-1234-1234-1234-123456789012"
        ),
        "jwt_audience": "api://nova",
        "jwt_issuer": "https://issuer.example.com/",
        "jwt_jwks_url": "https://issuer.example.com/.well-known/jwks.json",
    }


def _template(
    *,
    context: dict[str, str] | None = None,
    region: str = "us-west-2",
) -> Template:
    """Synthesize the runtime stack to a template for ingress assertions."""
    app = App(context=context or _context_for_region(region))
    stack = NovaRuntimeStack(
        app,
        "IngressContractStack",
        env=Environment(account="111111111111", region=region),
    )
    return Template.from_stack(stack)


def _resources_of_type(
    resources: dict[str, Any],
    type_name: str,
) -> dict[str, dict[str, Any]]:
    """Return all template resources of one CloudFormation type."""
    return {
        logical_id: resource
        for logical_id, resource in resources.items()
        if resource["Type"] == type_name
    }


def _template_json(
    *,
    context: dict[str, str] | None = None,
    region: str = "us-west-2",
) -> dict[str, Any]:
    """Return the synthesized template JSON for one stack context."""
    return cast(
        dict[str, Any], _template(context=context, region=region).to_json()
    )


def test_runtime_stack_uses_regional_rest_api_without_http_api() -> None:
    """The public ingress must be REST-only and free of CloudFront shims."""
    template_json = _template_json()
    resources = template_json["Resources"]

    assert not _resources_of_type(resources, "AWS::ApiGatewayV2::Api")
    assert not _resources_of_type(resources, "AWS::CloudFront::Distribution")

    rest_apis = _resources_of_type(resources, "AWS::ApiGateway::RestApi")
    assert len(rest_apis) == 1
    rest_api_props = next(iter(rest_apis.values()))["Properties"]
    assert rest_api_props["DisableExecuteApiEndpoint"] is True
    assert rest_api_props["EndpointConfiguration"]["Types"] == ["REGIONAL"]


def test_runtime_stack_configures_stage_logging_hooks() -> None:
    """API Gateway stage logging and metrics must remain enabled."""
    resources = _template_json()["Resources"]
    stages = _resources_of_type(resources, "AWS::ApiGateway::Stage")
    assert len(stages) == 1
    stage_props = next(iter(stages.values()))["Properties"]
    assert stage_props["StageName"] == "dev"
    assert stage_props["MethodSettings"] == [
        {
            "DataTraceEnabled": False,
            "HttpMethod": "*",
            "LoggingLevel": "ERROR",
            "MetricsEnabled": True,
            "ResourcePath": "/*",
        }
    ]
    access_log_setting = stage_props["AccessLogSetting"]
    assert "DestinationArn" in access_log_setting
    assert '"requestId":"$context.requestId"' in access_log_setting["Format"]
    assert '"httpMethod":"$context.httpMethod"' in access_log_setting["Format"]
    assert stage_props["TracingEnabled"] is True


def test_runtime_stack_associates_regional_waf_to_api_stage() -> None:
    """The WAF must bind directly to the regional REST API stage."""
    resources = _template_json()["Resources"]
    web_acls = _resources_of_type(resources, "AWS::WAFv2::WebACL")
    assert len(web_acls) == 1
    web_acl_props = next(iter(web_acls.values()))["Properties"]
    assert web_acl_props["Scope"] == "REGIONAL"
    assert (
        web_acl_props["VisibilityConfig"]["MetricName"] == "nova-rest-api-waf"
    )

    associations = _resources_of_type(
        resources,
        "AWS::WAFv2::WebACLAssociation",
    )
    assert len(associations) == 1
    association_text = json.dumps(
        next(iter(associations.values()))["Properties"],
        sort_keys=True,
    )
    assert "/restapis/" in association_text
    assert "/stages/dev" in association_text


def test_runtime_stack_exports_one_canonical_public_base_url() -> None:
    """Public base URL must be the canonical custom domain and nothing else."""
    outputs = _template_json()["Outputs"]
    public_base_url = outputs["ExportNovaPublicBaseUrl"]["Value"]
    assert public_base_url == ("https://api.dev.example.com")
    assert "ExportNovaCustomDomainName" not in outputs
    assert ".execute-api." not in public_base_url


def test_runtime_stack_creates_regional_custom_domain_mapping() -> None:
    """The custom domain must be regional and mapped as the root base path."""
    template_json = _template_json()
    resources = template_json["Resources"]

    domain_resources = _resources_of_type(
        resources,
        "AWS::ApiGateway::DomainName",
    )
    assert len(domain_resources) == 1
    domain_props = next(iter(domain_resources.values()))["Properties"]
    assert domain_props["DomainName"] == "api.dev.example.com"
    assert domain_props["EndpointConfiguration"]["Types"] == ["REGIONAL"]
    assert (
        domain_props["RegionalCertificateArn"]
        == _context_for_region("us-west-2")["certificate_arn"]
    )
    assert domain_props["SecurityPolicy"] == "TLS_1_2"

    mappings = _resources_of_type(
        resources,
        "AWS::ApiGateway::BasePathMapping",
    )
    assert len(mappings) == 1


def test_runtime_stack_keeps_proxy_ingress_and_required_route_contract() -> (
    None
):
    """Preserve the FastAPI route surface through the proxy-backed ingress."""
    resources = _template_json()["Resources"]
    methods = _resources_of_type(resources, "AWS::ApiGateway::Method")
    assert len(methods) == 2
    assert {
        (
            resource["Properties"]["HttpMethod"],
            resource["Properties"]["AuthorizationType"],
        )
        for resource in methods.values()
    } == {("ANY", "NONE")}

    proxy_resources = _resources_of_type(resources, "AWS::ApiGateway::Resource")
    assert len(proxy_resources) == 1
    assert (
        next(iter(proxy_resources.values()))["Properties"]["PathPart"]
        == "{proxy+}"
    )

    openapi_contract = json.loads(
        read_repo_file("packages/contracts/openapi/nova-file-api.openapi.json")
    )
    paths = openapi_contract["paths"]
    required_paths = {
        "/metrics/summary",
        "/v1/health/live",
        "/v1/health/ready",
        "/v1/exports",
        "/v1/transfers/uploads/initiate",
    }
    assert required_paths.issubset(paths)


@pytest.mark.parametrize("region", ["us-west-2", "eu-west-1"])
def test_runtime_stack_synthesizes_outside_us_east_1(region: str) -> None:
    """Regional REST ingress must not hard-fail outside us-east-1."""
    template_json = _template_json(
        context=_context_for_region(region),
        region=region,
    )
    outputs = template_json["Outputs"]
    assert outputs["ExportNovaPublicBaseUrl"]["Value"] == (
        "https://api.dev.example.com"
    )
