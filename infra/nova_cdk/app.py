# mypy: disable-error-code=import-not-found

"""CDK application entrypoint for the canonical Nova serverless stack."""

import json
import os

_RUNTIME_INPUT_HINTS: tuple[tuple[str, str], ...] = (
    ("api_domain_name", "API_DOMAIN_NAME"),
    ("api_lambda_artifact_bucket", "API_LAMBDA_ARTIFACT_BUCKET"),
    ("api_lambda_artifact_key", "API_LAMBDA_ARTIFACT_KEY"),
    ("certificate_arn", "CERTIFICATE_ARN"),
    ("jwt_issuer", "JWT_ISSUER"),
)


def _normalized_optional(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _load_cli_context_from_env() -> dict[str, object]:
    raw_context = os.environ.get("CDK_CONTEXT_JSON")
    if raw_context is None:
        return {}
    parsed_context = json.loads(raw_context)
    if not isinstance(parsed_context, dict):
        raise TypeError("CDK_CONTEXT_JSON must decode to a JSON object.")
    return parsed_context


CLI_CONTEXT = _load_cli_context_from_env()


def _preflight_context_or_env_value(key: str, env_var: str) -> str | None:
    context_value = _normalized_optional(CLI_CONTEXT.get(key))
    if context_value is not None:
        return context_value
    return _normalized_optional(os.environ.get(env_var))


def _runtime_inputs_requested_preflight() -> bool:
    return any(
        _preflight_context_or_env_value(key, env_var) is not None
        for key, env_var in _RUNTIME_INPUT_HINTS
    )


release_control_requested_preflight = all(
    _preflight_context_or_env_value(key, env_var) is not None
    for key, env_var in (
        ("release_github_owner", "RELEASE_GITHUB_OWNER"),
        ("release_github_repo", "RELEASE_GITHUB_REPO"),
        ("release_connection_arn", "RELEASE_CONNECTION_ARN"),
    )
)

if (
    not _runtime_inputs_requested_preflight()
    and not release_control_requested_preflight
):
    raise ValueError(
        "Provide runtime stack inputs or release-control inputs before "
        "synthesizing the Nova CDK app."
    )


def main() -> None:
    """Synthesize the requested Nova CDK stacks."""
    from aws_cdk import Annotations, App, Environment

    from nova_cdk.release_control_stack import (
        NovaReleaseControlPlaneStack,
        load_release_control_inputs,
    )
    from nova_cdk.release_support_stack import NovaReleaseSupportStack
    from nova_cdk.runtime_stack import NovaRuntimeStack

    app = App()

    def context_or_env_value(key: str, env_var: str) -> str | None:
        raw_value = app.node.try_get_context(key) or os.environ.get(env_var)
        return _normalized_optional(raw_value)

    account = context_or_env_value("account", "CDK_DEFAULT_ACCOUNT")
    region = context_or_env_value("region", "CDK_DEFAULT_REGION")
    if not account or not region:
        raise ValueError(
            "CDK account and region must be provided via -c account=... "
            "-c region=... or CDK_DEFAULT_ACCOUNT/CDK_DEFAULT_REGION."
        )

    runtime_inputs_requested = any(
        context_or_env_value(key, env_var) is not None
        for key, env_var in _RUNTIME_INPUT_HINTS
    )
    runtime_stack_id = (
        app.node.try_get_context("runtime_stack_id")
        or os.environ.get("RUNTIME_STACK_ID")
        or "NovaRuntimeStack"
    )
    release_github_owner = app.node.try_get_context(
        "release_github_owner"
    ) or os.environ.get("RELEASE_GITHUB_OWNER")
    release_github_repo = app.node.try_get_context(
        "release_github_repo"
    ) or os.environ.get("RELEASE_GITHUB_REPO")
    release_connection_arn = context_or_env_value(
        "release_connection_arn",
        "RELEASE_CONNECTION_ARN",
    )
    release_control_requested = bool(
        release_github_owner and release_github_repo and release_connection_arn
    )

    if runtime_inputs_requested:
        NovaRuntimeStack(
            app,
            runtime_stack_id,
            env=Environment(
                account=account,
                region=region,
            ),
        )

    if release_control_requested:
        dev_runtime_cfn_execution_role_arn = app.node.try_get_context(
            "dev_runtime_cfn_execution_role_arn"
        ) or os.environ.get("DEV_RUNTIME_CFN_EXECUTION_ROLE_ARN")
        prod_runtime_cfn_execution_role_arn = app.node.try_get_context(
            "prod_runtime_cfn_execution_role_arn"
        ) or os.environ.get("PROD_RUNTIME_CFN_EXECUTION_ROLE_ARN")
        if (
            not dev_runtime_cfn_execution_role_arn
            or not prod_runtime_cfn_execution_role_arn
        ):
            release_support_stack = NovaReleaseSupportStack(
                app,
                "NovaReleaseSupportStack",
                env=Environment(
                    account=account,
                    region=region,
                ),
            )
            dev_runtime_cfn_execution_role_arn = (
                dev_runtime_cfn_execution_role_arn
                or release_support_stack.dev_cfn_execution_role.role_arn
            )
            prod_runtime_cfn_execution_role_arn = (
                prod_runtime_cfn_execution_role_arn
                or release_support_stack.prod_cfn_execution_role.role_arn
            )
        NovaReleaseControlPlaneStack(
            app,
            "NovaReleaseControlPlaneStack",
            inputs=load_release_control_inputs(
                app,
                dev_cfn_execution_role_arn=dev_runtime_cfn_execution_role_arn,
                prod_cfn_execution_role_arn=prod_runtime_cfn_execution_role_arn,
            ),
            env=Environment(
                account=account,
                region=region,
            ),
        )

    Annotations.of(app).acknowledge_warning(
        "@aws-cdk/aws-lambda:codeFromBucketObjectVersionNotSpecified",
        "Nova uses immutable content-addressed API Lambda artifact keys plus "
        "deploy-output SHA256 provenance, so objectVersion is intentionally "
        "not threaded through the CDK surface.",
    )

    app.synth()


main()
