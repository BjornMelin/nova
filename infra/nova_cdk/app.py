# mypy: disable-error-code=import-not-found

"""CDK application entrypoint for the canonical Nova serverless stack."""

import os

from aws_cdk import Annotations, App, Environment

from nova_cdk.release_control_stack import (
    NovaReleaseControlPlaneStack,
    load_release_control_inputs,
)
from nova_cdk.release_support_stack import NovaReleaseSupportStack
from nova_cdk.runtime_stack import NovaRuntimeStack

app = App()

account = app.node.try_get_context("account") or os.environ.get(
    "CDK_DEFAULT_ACCOUNT"
)
region = app.node.try_get_context("region") or os.environ.get(
    "CDK_DEFAULT_REGION"
)
if not account or not region:
    raise ValueError(
        "CDK account and region must be provided via -c account=... "
        "-c region=... or CDK_DEFAULT_ACCOUNT/CDK_DEFAULT_REGION."
    )


def _context_or_env_value(key: str, env_var: str) -> str | None:
    raw_value = app.node.try_get_context(key) or os.environ.get(env_var)
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None


def _runtime_inputs_requested() -> bool:
    """Return whether any runtime-input hints are present.

    This is a lightweight heuristic used only for stack-selection flow:
    if any canonical runtime keys are provided via context or env, the app
    synthesizes the runtime stack path.
    """
    return any(
        _context_or_env_value(key, env_var) is not None
        for key, env_var in (
            ("api_domain_name", "API_DOMAIN_NAME"),
            ("api_lambda_artifact_bucket", "API_LAMBDA_ARTIFACT_BUCKET"),
            ("api_lambda_artifact_key", "API_LAMBDA_ARTIFACT_KEY"),
            ("certificate_arn", "CERTIFICATE_ARN"),
            ("jwt_issuer", "JWT_ISSUER"),
        )
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
release_control_requested = bool(release_github_owner and release_github_repo)

if _runtime_inputs_requested():
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

if not _runtime_inputs_requested() and not release_control_requested:
    raise ValueError(
        "Provide runtime stack inputs or release-control inputs before "
        "synthesizing the Nova CDK app."
    )

Annotations.of(app).acknowledge_warning(
    "@aws-cdk/aws-lambda:codeFromBucketObjectVersionNotSpecified",
    "Nova uses immutable content-addressed API Lambda artifact keys plus "
    "deploy-output SHA256 provenance, so objectVersion is intentionally not "
    "threaded through the CDK surface.",
)

app.synth()
