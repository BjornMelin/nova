"""CDK application entrypoint for the canonical Nova serverless stack."""

from aws_cdk import App, Environment
from nova_cdk.serverless_stack import NovaServerlessStack

app = App()

NovaServerlessStack(
    app,
    "NovaServerlessStack",
    env=Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region"),
    ),
)

app.synth()
