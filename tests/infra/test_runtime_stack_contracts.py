# mypy: disable-error-code=import-not-found

"""Contract tests for the canonical Nova runtime CDK stack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from .helpers import load_repo_package_module

_RUNTIME_STACK_MODULE = load_repo_package_module(
    "nova_cdk.runtime_stack",
    "infra/nova_cdk/src",
)
NovaRuntimeStack = _RUNTIME_STACK_MODULE.NovaRuntimeStack


def _context_for_region(region: str) -> dict[str, str]:
    """Return the minimum valid stack context for one region."""
    return {
        "api_domain_name": "api.dev.example.com",
        "api_lambda_artifact_bucket": (
            "nova-ci-artifacts-111111111111-us-east-1"
        ),
        "api_lambda_artifact_key": (
            "runtime/nova-file-api/"
            "01234567-89ab-cdef-0123-456789abcdef/"
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef/"
            "nova-file-api-lambda.zip"
        ),
        "api_lambda_artifact_sha256": (
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
        "certificate_arn": (
            f"arn:aws:acm:{region}:111111111111:"
            "certificate/12345678-1234-1234-1234-123456789012"
        ),
        "hosted_zone_id": "Z1234567890EXAMPLE",
        "hosted_zone_name": "example.com",
        "jwt_audience": "api://nova",
        "jwt_issuer": "https://issuer.example.com/",
        "jwt_jwks_url": "https://issuer.example.com/.well-known/jwks.json",
    }


@dataclass(frozen=True)
class _TemplateBundle:
    """Hold the template fragments used by runtime contract tests."""

    api_function_env: dict[str, str]
    definition_fragment: str
    outputs: dict[str, Any]
    resources: dict[str, Any]


def _template(
    *,
    context: dict[str, str] | None = None,
    region: str = "us-west-2",
) -> Template:
    """Synthesize the runtime stack to a template for assertions."""
    app = App(context=context or _context_for_region(region))
    stack = NovaRuntimeStack(
        app,
        "RuntimeContractStack",
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


def _api_function_env(resources: dict[str, Any]) -> dict[str, str]:
    """Return the API Lambda environment block from the synthesized template."""
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
    """Return the rendered Step Functions JSON fragment for assertions."""
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


def _build_bundle(
    *,
    context: dict[str, str] | None = None,
    region: str = "us-west-2",
) -> _TemplateBundle:
    """Build a reusable template bundle for runtime assertions."""
    template_json = _template(context=context, region=region).to_json()
    resources = template_json["Resources"]
    return _TemplateBundle(
        api_function_env=_api_function_env(resources),
        definition_fragment=_definition_fragment(resources),
        outputs=template_json["Outputs"],
        resources=resources,
    )


@pytest.mark.parametrize(
    "missing_key",
    [
        "api_domain_name",
        "api_lambda_artifact_bucket",
        "api_lambda_artifact_key",
        "api_lambda_artifact_sha256",
        "certificate_arn",
        "hosted_zone_id",
        "hosted_zone_name",
        "jwt_audience",
        "jwt_issuer",
        "jwt_jwks_url",
    ],
)
def test_runtime_stack_requires_complete_context(missing_key: str) -> None:
    """Runtime synth must fail closed on incomplete stack inputs."""
    context = _context_for_region("us-west-2")
    context.pop(missing_key)

    with pytest.raises(ValueError, match=missing_key):
        _template(context=context)


def test_runtime_stack_passes_oidc_env_to_api_lambda() -> None:
    """API Lambda must receive the in-process OIDC verifier settings."""
    bundle = _build_bundle()
    api_function_env = bundle.api_function_env
    assert api_function_env["OIDC_ISSUER"] == "https://issuer.example.com/"
    assert api_function_env["OIDC_AUDIENCE"] == "api://nova"
    assert (
        api_function_env["OIDC_JWKS_URL"]
        == "https://issuer.example.com/.well-known/jwks.json"
    )


def test_runtime_stack_maps_caught_errors_for_failure_handler() -> None:
    """Route workflow failure fields to the fail handler input payload."""
    bundle = _build_bundle()
    definition_fragment = bundle.definition_fragment
    assert "$.workflow_error.Error" in definition_fragment
    assert "$.workflow_error.Cause" in definition_fragment
    assert "$.workflow_error" in definition_fragment
    assert '"status":"failed"' in definition_fragment
    assert '"updated_at.$":"$.updated_at"' in definition_fragment


def test_runtime_stack_packages_api_lambda_as_native_zip() -> None:
    """API Lambda should use zip packaging and the native handler."""
    bundle = _build_bundle()
    functions = _resources_of_type(bundle.resources, "AWS::Lambda::Function")
    api_resource = next(
        resource
        for resource in functions.values()
        if (
            resource["Properties"]
            .get("Environment", {})
            .get("Variables", {})
            .get("JOBS_STEP_FUNCTIONS_STATE_MACHINE_ARN")
        )
    )
    props = api_resource["Properties"]
    assert props["Handler"] == "nova_file_api.lambda_handler.handler"
    assert props["Runtime"] == "python3.13"
    assert "ReservedConcurrentExecutions" not in props
    assert "S3Bucket" in props["Code"]
    assert (
        props["Code"]["S3Key"]
        == _context_for_region("us-west-2")["api_lambda_artifact_key"]
    )
    assert "ImageUri" not in props.get("Code", {})
    assert (
        props["Environment"]["Variables"]["API_RELEASE_ARTIFACT_SHA256"]
        == _context_for_region("us-west-2")["api_lambda_artifact_sha256"]
    )

    policies = _resources_of_type(bundle.resources, "AWS::IAM::Policy")
    policy_fragments = [
        str(resource["Properties"]["PolicyDocument"])
        for resource in policies.values()
    ]
    assert any(
        "states:DescribeStateMachine" in fragment
        for fragment in policy_fragments
    )


def test_runtime_stack_uses_higher_reserved_concurrency_default_in_prod() -> (
    None
):
    """Prod stacks should retain the bounded higher concurrency default."""
    context = {
        **_context_for_region("us-west-2"),
        "environment": "prod",
        "allowed_origins": '["https://app.example.com"]',
    }
    bundle = _build_bundle(context=context)
    functions = _resources_of_type(bundle.resources, "AWS::Lambda::Function")
    api_resource = next(
        resource
        for resource in functions.values()
        if (
            resource["Properties"]
            .get("Environment", {})
            .get("Variables", {})
            .get("JOBS_STEP_FUNCTIONS_STATE_MACHINE_ARN")
        )
    )
    assert api_resource["Properties"]["ReservedConcurrentExecutions"] == 25


def test_runtime_stack_adds_s3_abort_incomplete_multipart_lifecycle() -> None:
    """The transfer bucket should abort incomplete multipart uploads."""
    bundle = _build_bundle()
    buckets = _resources_of_type(bundle.resources, "AWS::S3::Bucket")
    assert buckets
    bucket_props = next(iter(buckets.values()))["Properties"]
    rules = bucket_props["LifecycleConfiguration"]["Rules"]
    assert (
        rules[0]["AbortIncompleteMultipartUpload"]["DaysAfterInitiation"] == 7
    )
