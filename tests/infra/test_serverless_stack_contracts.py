"""Contract tests for the canonical Nova serverless CDK stack."""

from __future__ import annotations

import json
from dataclasses import dataclass

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


@dataclass(frozen=True)
class _DefaultTemplateBundle:
    api_function_env: dict[str, str]
    routes: dict[str, dict[str, object]]
    definition_fragment: str


def _template(
    *,
    context: dict[str, str] | None = None,
) -> Template:
    app = App(context=context or dict(_BASE_CONTEXT))
    stack = NovaServerlessStack(
        app,
        "ServerlessContractStack",
        env=Environment(account="111111111111", region="us-east-1"),
    )
    return Template.from_stack(stack)


def _route_properties(template: Template) -> dict[str, dict[str, object]]:
    routes = template.find_resources("AWS::ApiGatewayV2::Route")
    return {
        properties["RouteKey"]: properties
        for properties in (
            resource["Properties"] for resource in routes.values()
        )
    }


def _state_machine_definition_text(template: Template) -> str:
    resources = template.find_resources("AWS::StepFunctions::StateMachine")
    assert len(resources) == 1
    return json.dumps(next(iter(resources.values())), sort_keys=True)


@pytest.fixture(scope="module")
def default_template_bundle() -> _DefaultTemplateBundle:
    """Synthesize the default stack once for the positive-path assertions."""
    template = _template()
    functions = template.find_resources("AWS::Lambda::Function")

    api_function_env: dict[str, str] | None = None
    for resource in functions.values():
        environment = resource["Properties"].get("Environment")
        if not isinstance(environment, dict):
            continue
        variables = environment.get("Variables")
        if not isinstance(variables, dict):
            continue
        if "JOBS_STEP_FUNCTIONS_STATE_MACHINE_ARN" in variables:
            api_function_env = variables
            break

    assert api_function_env is not None
    definition_text = _state_machine_definition_text(template)
    resource = json.loads(definition_text)
    definition_fragment = "".join(
        part
        for part in resource["Properties"]["DefinitionString"]["Fn::Join"][1]
        if isinstance(part, str)
    )

    return _DefaultTemplateBundle(
        api_function_env=api_function_env,
        routes=_route_properties(template),
        definition_fragment=definition_fragment,
    )


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
    default_template_bundle: _DefaultTemplateBundle,
) -> None:
    """API Lambda must receive the in-process OIDC verifier settings."""
    api_function_env = default_template_bundle.api_function_env
    assert api_function_env["OIDC_ISSUER"] == _BASE_CONTEXT["jwt_issuer"]
    assert api_function_env["OIDC_AUDIENCE"] == _BASE_CONTEXT["jwt_audience"]
    assert api_function_env["OIDC_JWKS_URL"] == _BASE_CONTEXT["jwt_jwks_url"]


def test_serverless_stack_keeps_health_routes_public(
    default_template_bundle: _DefaultTemplateBundle,
) -> None:
    """Health probes must stay unauthenticated while /v1 stays JWT-protected."""
    routes = default_template_bundle.routes
    assert routes["GET /v1/health/live"]["AuthorizationType"] == "NONE"
    assert routes["GET /v1/health/ready"]["AuthorizationType"] == "NONE"
    assert routes["ANY /v1"]["AuthorizationType"] == "JWT"
    assert routes["ANY /v1/{proxy+}"]["AuthorizationType"] == "JWT"
    assert "AuthorizerId" not in routes["GET /v1/health/live"]
    assert "AuthorizerId" not in routes["GET /v1/health/ready"]
    assert "AuthorizerId" in routes["ANY /v1"]
    assert "AuthorizerId" in routes["ANY /v1/{proxy+}"]


def test_serverless_stack_maps_caught_errors_for_failure_handler(
    default_template_bundle: _DefaultTemplateBundle,
) -> None:
    """Workflow failures must reach the fail handler as top-level fields."""
    definition_fragment = default_template_bundle.definition_fragment
    assert "$.workflow_error.Error" in definition_fragment
    assert "$.workflow_error.Cause" in definition_fragment
    assert "$.workflow_error" in definition_fragment
    assert '"status":"failed"' in definition_fragment
    assert '"updated_at.$":"$.updated_at"' in definition_fragment
