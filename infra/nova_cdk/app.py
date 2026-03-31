# mypy: disable-error-code=import-not-found

"""CDK application entrypoint for the canonical Nova serverless stack."""

import os

from aws_cdk import Annotations, App, Environment

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

NovaRuntimeStack(
    app,
    "NovaRuntimeStack",
    env=Environment(
        account=account,
        region=region,
    ),
)

Annotations.of(app).acknowledge_warning(
    "@aws-cdk/aws-lambda:codeFromBucketObjectVersionNotSpecified",
    "Nova uses immutable content-addressed API Lambda artifact keys plus "
    "deploy-output SHA256 provenance, so objectVersion is intentionally not "
    "threaded through the CDK surface.",
)

app.synth()
