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
    try:
        parsed_context = json.loads(raw_context)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "CDK_CONTEXT_JSON must contain a valid JSON object."
        ) from exc
    if not isinstance(parsed_context, dict):
        raise TypeError("CDK_CONTEXT_JSON must decode to a JSON object.")
    return parsed_context


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
    cli_context = _load_cli_context_from_env()

    def context_or_env_value(key: str, env_var: str) -> str | None:
        raw_value = app.node.try_get_context(key)
        if raw_value is None:
            raw_value = cli_context.get(key)
        if raw_value is None:
            raw_value = os.environ.get(env_var)
        return _normalized_optional(raw_value)

    runtime_inputs_requested = any(
        context_or_env_value(key, env_var) is not None
        for key, env_var in _RUNTIME_INPUT_HINTS
    )
    release_github_owner = context_or_env_value(
        "release_github_owner",
        "RELEASE_GITHUB_OWNER",
    )
    release_github_repo = context_or_env_value(
        "release_github_repo",
        "RELEASE_GITHUB_REPO",
    )
    release_connection_arn = context_or_env_value(
        "release_connection_arn",
        "RELEASE_CONNECTION_ARN",
    )
    release_control_requested = bool(
        release_github_owner and release_github_repo and release_connection_arn
    )
    if not runtime_inputs_requested and not release_control_requested:
        raise ValueError(
            "Provide runtime stack inputs or release-control inputs before "
            "synthesizing the Nova CDK app."
        )

    account = context_or_env_value("account", "CDK_DEFAULT_ACCOUNT")
    region = context_or_env_value("region", "CDK_DEFAULT_REGION")
    if not account or not region:
        raise ValueError(
            "CDK account and region must be provided via -c account=... "
            "-c region=... or CDK_DEFAULT_ACCOUNT/CDK_DEFAULT_REGION."
        )

    runtime_stack_id = (
        context_or_env_value("runtime_stack_id", "RUNTIME_STACK_ID")
        or "NovaRuntimeStack"
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
        release_support_stack_id: str | None = None
        dev_runtime_cfn_execution_role_arn = context_or_env_value(
            "dev_runtime_cfn_execution_role_arn",
            "DEV_RUNTIME_CFN_EXECUTION_ROLE_ARN",
        )
        prod_runtime_cfn_execution_role_arn = context_or_env_value(
            "prod_runtime_cfn_execution_role_arn",
            "PROD_RUNTIME_CFN_EXECUTION_ROLE_ARN",
        )
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
            release_support_stack_id = release_support_stack.stack_name
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
                support_stack_id=release_support_stack_id,
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


if __name__ == "__main__":
    main()
