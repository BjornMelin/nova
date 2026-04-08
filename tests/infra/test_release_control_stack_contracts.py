"""Contract tests for the AWS-native Nova release control-plane stack."""

from __future__ import annotations

from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from .helpers import load_repo_package_module, resources_of_type

_STACK_MODULE = load_repo_package_module(
    "nova_cdk.release_control_stack",
    "infra/nova_cdk/src",
)
NovaReleaseControlPlaneStack = _STACK_MODULE.NovaReleaseControlPlaneStack


def _context() -> dict[str, str]:
    return {
        "release_github_owner": "BjornMelin",
        "release_github_repo": "nova",
        "release_connection_arn": (
            "arn:aws:codeconnections:us-east-1:111111111111:"
            "connection/12345678-1234-1234-1234-123456789012"
        ),
        "release_signing_secret_id": "nova/release/signing",
        "codeartifact_domain": "nova-internal",
        "codeartifact_staging_repository": "nova-staging",
        "codeartifact_prod_repository": "nova-prod",
        "dev_runtime_cfn_execution_role_arn": (
            "arn:aws:iam::111111111111:role/nova-dev-cfn"
        ),
        "dev_runtime_config_parameter_name": (
            "/nova/release/runtime-config/dev"
        ),
        "release_support_stack_id": "NovaReleaseSupportStack",
        "prod_runtime_stack_id": "NovaRuntimeProdStack",
        "prod_runtime_cfn_execution_role_arn": (
            "arn:aws:iam::111111111111:role/nova-prod-cfn"
        ),
        "prod_runtime_config_parameter_name": (
            "/nova/release/runtime-config/prod"
        ),
        "release_approval_email": "nova-release@example.com",
    }


def _template() -> Template:
    app = App(context=_context())
    stack = NovaReleaseControlPlaneStack(
        app,
        "ReleaseControlContractStack",
        env=Environment(account="111111111111", region="us-east-1"),
    )
    return Template.from_stack(stack)


def test_release_control_plane_stack_synthesizes_required_resources() -> None:
    template = _template().to_json()
    resources = template["Resources"]

    assert resources_of_type(resources, "AWS::CodePipeline::Pipeline")
    assert resources_of_type(resources, "AWS::CodeBuild::Project")
    assert resources_of_type(resources, "AWS::S3::Bucket")


def test_release_control_plane_stack_wires_manual_prod_approval() -> None:
    template = _template().to_json()
    pipeline_resources = resources_of_type(
        template["Resources"], "AWS::CodePipeline::Pipeline"
    )
    assert len(pipeline_resources) == 1
    pipeline = next(iter(pipeline_resources.values()))
    stages = pipeline["Properties"]["Stages"]
    stage_names = [stage["Name"] for stage in stages]
    assert stage_names == [
        "Source",
        "ValidateReleasePrep",
        "PublishAndDeployDev",
        "ApproveProd",
        "PromoteAndDeployProd",
    ]


def test_release_control_stack_injects_pipeline_execution_id() -> None:
    template = _template().to_json()
    pipeline_resources = resources_of_type(
        template["Resources"], "AWS::CodePipeline::Pipeline"
    )
    pipeline = next(iter(pipeline_resources.values()))
    stages = {
        stage["Name"]: stage["Actions"]
        for stage in pipeline["Properties"]["Stages"]
    }

    for stage_name in ["PublishAndDeployDev", "PromoteAndDeployProd"]:
        action = stages[stage_name][0]
        environment_variables = action["Configuration"]["EnvironmentVariables"]
        assert "CODEPIPELINE_EXECUTION_ID" in environment_variables
        assert "#{codepipeline.PipelineExecutionId}" in environment_variables


def test_release_control_stack_receives_release_env_contract() -> None:
    template = _template().to_json()
    projects = resources_of_type(
        template["Resources"], "AWS::CodeBuild::Project"
    )
    env_var_names = {
        str(environment_variable.get("Name"))
        for project in projects.values()
        for environment_variable in project["Properties"]
        .get("Environment", {})
        .get("EnvironmentVariables", [])
        if isinstance(environment_variable, dict)
        and "Name" in environment_variable
    }
    for required in [
        "RELEASE_ARTIFACT_BUCKET",
        "RELEASE_MANIFEST_BUCKET",
        "CODEARTIFACT_DOMAIN",
        "CODEARTIFACT_STAGING_REPOSITORY",
        "CODEARTIFACT_PROD_REPOSITORY",
        "RELEASE_GITHUB_OWNER",
        "RELEASE_GITHUB_REPO",
        "RELEASE_PIPELINE_NAME",
        "DEV_RUNTIME_STACK_ID",
        "PROD_RUNTIME_STACK_ID",
        "DEV_RUNTIME_CONFIG_PARAMETER_NAME",
        "PROD_RUNTIME_CONFIG_PARAMETER_NAME",
        "DEV_RUNTIME_CFN_EXECUTION_ROLE_NAME",
        "PROD_RUNTIME_CFN_EXECUTION_ROLE_NAME",
        "RELEASE_SUPPORT_STACK_ID",
        "RELEASE_SIGNING_SECRET_ID",
    ]:
        assert required in env_var_names


def test_release_control_stack_scopes_dev_and_prod_permissions() -> None:
    template = _template().to_json()
    resources = template["Resources"]
    projects = resources_of_type(resources, "AWS::CodeBuild::Project")

    dev_project = next(
        project
        for project in projects.values()
        if {
            environment_variable.get("Name")
            for environment_variable in project["Properties"]
            .get("Environment", {})
            .get("EnvironmentVariables", [])
            if isinstance(environment_variable, dict)
        }
        >= {"DEV_RUNTIME_STACK_ID"}
    )
    prod_project = next(
        project
        for project in projects.values()
        if {
            environment_variable.get("Name")
            for environment_variable in project["Properties"]
            .get("Environment", {})
            .get("EnvironmentVariables", [])
            if isinstance(environment_variable, dict)
        }
        >= {"PROD_RUNTIME_STACK_ID"}
    )

    dev_env_vars = {
        environment_variable.get("Name")
        for environment_variable in dev_project["Properties"]
        .get("Environment", {})
        .get("EnvironmentVariables", [])
        if isinstance(environment_variable, dict)
    }
    prod_env_vars = {
        environment_variable.get("Name")
        for environment_variable in prod_project["Properties"]
        .get("Environment", {})
        .get("EnvironmentVariables", [])
        if isinstance(environment_variable, dict)
    }

    assert "CODEARTIFACT_PROD_REPOSITORY" not in dev_env_vars
    assert "RELEASE_SIGNING_SECRET_ID" in dev_env_vars
    assert "CODEARTIFACT_PROD_REPOSITORY" in prod_env_vars
    assert "RELEASE_SIGNING_SECRET_ID" not in prod_env_vars

    policies = resources_of_type(resources, "AWS::IAM::Policy")
    dev_role_policy = next(
        policy
        for policy in policies.values()
        if "PublishAndDeployDevProjectRole"
        in str(policy["Properties"].get("Roles", []))
    )
    prod_role_policy = next(
        policy
        for policy in policies.values()
        if "PromoteAndDeployProdProjectRole"
        in str(policy["Properties"].get("Roles", []))
    )
    dev_policy_text = str(dev_role_policy["Properties"]["PolicyDocument"])
    prod_policy_text = str(prod_role_policy["Properties"]["PolicyDocument"])

    assert "nova-dev-cfn" in dev_policy_text
    assert "nova-prod-cfn" not in dev_policy_text
    assert "nova-prod-cfn" in prod_policy_text
    assert "nova-dev-cfn" not in prod_policy_text
    assert "parameter/cdk-bootstrap/hnb659fds/version" in dev_policy_text
    assert "parameter/cdk-bootstrap/hnb659fds/version" in prod_policy_text
    assert "stack/NovaReleaseSupportStack/" in dev_policy_text
    assert "stack/NovaReleaseSupportStack/" in prod_policy_text
