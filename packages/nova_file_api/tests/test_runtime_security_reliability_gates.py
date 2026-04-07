from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.runtime_gate

_API_DOCKERFILE = REPO_ROOT / "apps" / "nova_file_api_service" / "Dockerfile"
_WORKFLOW_TASK_DOCKERFILE = (
    REPO_ROOT / "apps" / "nova_workflows_tasks" / "Dockerfile"
)
_API_ASSET_BUILDER = (
    REPO_ROOT / "scripts" / "release" / "build_api_lambda_asset.py"
)
_WORKFLOW_ASSET_BUILDER = (
    REPO_ROOT / "scripts" / "release" / "build_workflow_lambda_asset.py"
)
_DOCKER_RELEASE_GATE = (
    REPO_ROOT / "scripts" / "checks" / "run_docker_release_images.sh"
)
_RELEASE_BUILD_BUILDSPEC = (
    REPO_ROOT
    / "infra"
    / "nova_cdk"
    / "buildspecs"
    / "release-publish-and-deploy-dev.yml"
)


def test_api_runtime_uses_zip_packaging_instead_of_service_dockerfile() -> None:
    """The public API runtime should no longer ship as a Docker image."""
    assert not _API_DOCKERFILE.exists()
    assert _API_ASSET_BUILDER.exists()


def test_aws_release_build_owns_api_lambda_packaging() -> None:
    """AWS release execution should own API Lambda packaging."""
    content = _RELEASE_BUILD_BUILDSPEC.read_text(encoding="utf-8")

    assert "python -m scripts.release.build_api_lambda_asset" in content
    assert "--output-zip .release-control/nova-file-api-lambda.zip" in content
    assert "api-lambda-artifact.json" in content
    assert "release-execution-manifest.json" in content
    assert "aws s3 cp" in content


def test_aws_release_build_owns_workflow_lambda_packaging() -> None:
    """AWS release execution should own workflow Lambda packaging."""
    content = _RELEASE_BUILD_BUILDSPEC.read_text(encoding="utf-8")

    assert _WORKFLOW_ASSET_BUILDER.exists()
    assert "python -m scripts.release.build_workflow_lambda_asset" in content
    assert "--output-zip .release-control/nova-workflows-lambda.zip" in content
    assert "workflow-lambda-artifact.json" in content


def test_workflow_task_dockerfile_remains_lambda_native() -> None:
    """Remaining workflow-task builds should stay on Lambda base images."""
    content = _WORKFLOW_TASK_DOCKERFILE.read_text(encoding="utf-8")

    assert content.startswith("# syntax=docker/dockerfile:")
    assert "FROM public.ecr.aws/lambda/python:3.13" in content
    assert "COPY --from=ghcr.io/astral-sh/uv:" in content
    assert '"uvicorn"' not in content
    assert "lambda-adapter" not in content


def test_docker_release_gate_targets_workflow_tasks_only() -> None:
    """Release-image verification should no longer reference the API image."""
    content = _DOCKER_RELEASE_GATE.read_text(encoding="utf-8")

    assert "apps/nova_workflows_tasks/Dockerfile" in content
    assert "apps/nova_file_api_service/Dockerfile" not in content
    assert "test_workflow_productization_contracts.py" not in content


def test_service_packages_declare_native_runtime_dependencies() -> None:
    """Assert service packages declare native runtime dependencies."""
    package_path = REPO_ROOT / "packages" / "nova_file_api" / "pyproject.toml"

    payload = tomllib.loads(package_path.read_text(encoding="utf-8"))
    dependencies = payload["project"]["dependencies"]
    assert "anyio>=4.13.0" in dependencies
    assert "fastapi>=0.135.3" in dependencies
    assert "nova-runtime-support>=0.1.0" in dependencies
    assert "mangum>=0.21.0" in dependencies
    assert "httpx>=0.28.1" not in dependencies


def test_workspace_dev_group_keeps_httpx_for_test_and_tooling_surfaces() -> (
    None
):
    """Workspace dev tooling should carry httpx for tests and perf helpers."""
    payload = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert "httpx>=0.28.1" in payload["dependency-groups"]["dev"]
