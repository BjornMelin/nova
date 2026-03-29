"""Contract tests for the canonical Nova serverless CDK stack."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from .helpers import load_repo_module

_SERVERLESS_STACK_MODULE = load_repo_module(
    "tests.infra.serverless_stack_contracts_module",
    "infra/nova_cdk/src/nova_cdk/serverless_stack.py",
)
NovaServerlessStack = _SERVERLESS_STACK_MODULE.NovaServerlessStack

_BASE_CONTEXT = {
    "jwt_issuer": "https://issuer.example.com/",
    "jwt_audience": "api://nova",
    "jwt_jwks_url": "https://issuer.example.com/.well-known/jwks.json",
}
_CUSTOM_DOMAIN_CONTEXT = {
    "api_custom_domain_name": "api.example.com",
    "api_certificate_arn": (
        "arn:aws:acm:us-west-2:111111111111:"
        "certificate/12345678-1234-1234-1234-123456789012"
    ),
}


@dataclass(frozen=True)
class _TemplateBundle:
    api_function_env: dict[str, str]
    outputs: dict[str, Any]
    resources: dict[str, Any]
    definition_fragment: str


def _template(
    *,
    context: dict[str, str] | None = None,
    region: str = "us-west-2",
) -> Template:
    app = App(context=context or dict(_BASE_CONTEXT))
    stack = NovaServerlessStack(
        app,
        "ServerlessContractStack",
        env=Environment(account="111111111111", region=region),
    )
    return Template.from_stack(stack)


def _resources_of_type(
    resources: dict[str, Any],
    type_name: str,
) -> dict[str, dict[str, Any]]:
    return {
        logical_id: resource
        for logical_id, resource in resources.items()
        if resource["Type"] == type_name
    }


def _api_function_env(resources: dict[str, Any]) -> dict[str, str]:
    functions = _resources_of_type(resources, "AWS::Lambda::Function")
    for resource in functions.values():
        variables = (
            resource["Properties"].get("Environment", {}).get("Variables")
        )
        if isinstance(variables, dict) and (
            "JOBS_STEP_FUNCTIONS_STATE_MACHINE_ARN" in variables
        ):
            return variables
    raise AssertionError("Could not locate the API Lambda environment block")


def _definition_fragment(resources: dict[str, Any]) -> str:
    state_machines = _resources_of_type(
        resources,
        "AWS::StepFunctions::StateMachine",
    )
    assert len(state_machines) == 1
    resource = next(iter(state_machines.values()))
    return "".join(
        part
        for part in resource["Properties"]["DefinitionString"]["Fn::Join"][1]
        if isinstance(part, str)
    )


def _build_bundle(*, context: dict[str, str] | None = None) -> _TemplateBundle:
    template_json = _template(context=context).to_json()
    resources = template_json["Resources"]
    return _TemplateBundle(
        api_function_env=_api_function_env(resources),
        outputs=template_json["Outputs"],
        resources=resources,
        definition_fragment=_definition_fragment(resources),
    )


@pytest.fixture(scope="module")
def default_template_bundle() -> _TemplateBundle:
    return _build_bundle()


@pytest.fixture(scope="module")
def custom_domain_template_bundle() -> _TemplateBundle:
    return _build_bundle(context={**_BASE_CONTEXT, **_CUSTOM_DOMAIN_CONTEXT})


@pytest.mark.parametrize(
    "missing_key",
    ["jwt_issuer", "jwt_audience", "jwt_jwks_url"],
)
def test_serverless_stack_requires_complete_oidc_context(
    missing_key: str,
) -> None:
    """Serverless synth must fail closed on incomplete OIDC wiring."""
    context = dict(_BASE_CONTEXT)
    context.pop(missing_key)

    with pytest.raises(ValueError, match=missing_key):
        _template(context=context)


def test_serverless_stack_passes_oidc_env_to_api_lambda(
    default_template_bundle: _TemplateBundle,
) -> None:
    """API Lambda must receive the in-process OIDC verifier settings."""
    api_function_env = default_template_bundle.api_function_env
    assert api_function_env["OIDC_ISSUER"] == _BASE_CONTEXT["jwt_issuer"]
    assert api_function_env["OIDC_AUDIENCE"] == _BASE_CONTEXT["jwt_audience"]
    assert api_function_env["OIDC_JWKS_URL"] == _BASE_CONTEXT["jwt_jwks_url"]


def test_serverless_stack_uses_regional_rest_api_and_not_cloudfront(
    default_template_bundle: _TemplateBundle,
) -> None:
    """The canonical ingress is a regional REST API with execute-api enabled."""
    resources = default_template_bundle.resources
    assert not _resources_of_type(resources, "AWS::ApiGatewayV2::Api")
    assert not _resources_of_type(resources, "AWS::CloudFront::Distribution")

    rest_apis = _resources_of_type(resources, "AWS::ApiGateway::RestApi")
    assert len(rest_apis) == 1
    rest_api_props = next(iter(rest_apis.values()))["Properties"]
    assert rest_api_props["DisableExecuteApiEndpoint"] is False
    assert rest_api_props["EndpointConfiguration"]["Types"] == ["REGIONAL"]


def test_serverless_stack_configures_stage_logging_hooks(
    default_template_bundle: _TemplateBundle,
) -> None:
    """API Gateway stage logging and metrics must be enabled in synth output."""
    stages = _resources_of_type(
        default_template_bundle.resources,
        "AWS::ApiGateway::Stage",
    )
    assert len(stages) == 1
    stage_props = next(iter(stages.values()))["Properties"]
    assert stage_props["StageName"] == "dev"
    method_settings = stage_props["MethodSettings"]
    assert method_settings == [
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


def test_serverless_stack_associates_regional_waf_to_api_stage(
    default_template_bundle: _TemplateBundle,
) -> None:
    """The WAF must bind directly to the REST API stage, not CloudFront."""
    resources = default_template_bundle.resources
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


def test_serverless_stack_keeps_proxy_method_support(
    default_template_bundle: _TemplateBundle,
) -> None:
    """Expose root and greedy-proxy ANY methods so FastAPI paths stay intact."""
    resources = default_template_bundle.resources
    methods = _resources_of_type(resources, "AWS::ApiGateway::Method")
    assert len(methods) == 2
    method_pairs = {
        (
            resource["Properties"]["HttpMethod"],
            resource["Properties"]["AuthorizationType"],
        )
        for resource in methods.values()
    }
    assert method_pairs == {("ANY", "NONE")}

    proxy_resources = _resources_of_type(resources, "AWS::ApiGateway::Resource")
    assert len(proxy_resources) == 1
    assert (
        next(iter(proxy_resources.values()))["Properties"]["PathPart"]
        == "{proxy+}"
    )


def test_serverless_stack_exports_one_canonical_public_base_url(
    default_template_bundle: _TemplateBundle,
) -> None:
    """Default synth keeps only the regional stage URL."""
    outputs = default_template_bundle.outputs
    assert outputs["ExportNovaCustomDomainName"]["Value"] == ""
    public_base_url = json.dumps(
        outputs["ExportNovaPublicBaseUrl"]["Value"],
        sort_keys=True,
    )
    assert ".execute-api." in public_base_url
    assert "/dev" in public_base_url
    assert "cloudfront" not in public_base_url.lower()
    assert not _resources_of_type(
        default_template_bundle.resources,
        "AWS::ApiGateway::DomainName",
    )
    assert not _resources_of_type(
        default_template_bundle.resources,
        "AWS::ApiGateway::BasePathMapping",
    )


def test_serverless_stack_supports_optional_custom_domain(
    custom_domain_template_bundle: _TemplateBundle,
) -> None:
    """Optional domain config adds API Gateway domain resources and outputs."""
    outputs = custom_domain_template_bundle.outputs
    assert outputs["ExportNovaCustomDomainName"]["Value"] == "api.example.com"
    assert (
        outputs["ExportNovaPublicBaseUrl"]["Value"] == "https://api.example.com"
    )

    domain_resources = _resources_of_type(
        custom_domain_template_bundle.resources,
        "AWS::ApiGateway::DomainName",
    )
    assert len(domain_resources) == 1
    domain_props = next(iter(domain_resources.values()))["Properties"]
    assert domain_props["DomainName"] == "api.example.com"
    assert domain_props["EndpointConfiguration"]["Types"] == ["REGIONAL"]
    assert (
        domain_props["RegionalCertificateArn"]
        == _CUSTOM_DOMAIN_CONTEXT["api_certificate_arn"]
    )
    assert domain_props["SecurityPolicy"] == "TLS_1_2"

    mappings = _resources_of_type(
        custom_domain_template_bundle.resources,
        "AWS::ApiGateway::BasePathMapping",
    )
    assert len(mappings) == 1


def test_serverless_stack_maps_caught_errors_for_failure_handler(
    default_template_bundle: _TemplateBundle,
) -> None:
    """Route workflow failure fields to the fail handler input payload."""
    definition_fragment = default_template_bundle.definition_fragment
    assert "$.workflow_error.Error" in definition_fragment
    assert "$.workflow_error.Cause" in definition_fragment
    assert "$.workflow_error" in definition_fragment
    assert '"status":"failed"' in definition_fragment
    assert '"updated_at.$":"$.updated_at"' in definition_fragment
