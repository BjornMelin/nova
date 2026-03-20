from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

_SERVICE_DOCKERFILES = (
    REPO_ROOT / "apps" / "nova_file_api_service" / "Dockerfile",
)
_ASYNC_TEMPLATE = (
    REPO_ROOT / "infra" / "runtime" / "file_transfer" / "async.yml"
)
_RELEASE_BUILDSPEC = REPO_ROOT / "buildspecs" / "buildspec-release.yml"


def test_service_dockerfiles_enforce_proxy_headers_and_single_process() -> None:
    for dockerfile in _SERVICE_DOCKERFILES:
        content = dockerfile.read_text(encoding="utf-8")

        assert content.startswith("# syntax=docker/dockerfile:")
        assert "COPY --from=ghcr.io/astral-sh/uv:" in content
        assert "--mount=type=cache,target=/root/.cache/uv" in content
        assert '"uvicorn"' in content
        assert "--proxy-headers" in content
        assert "--forwarded-allow-ips=*" in content
        assert "HEALTHCHECK" in content
        assert "--workers" not in content
        assert "gunicorn" not in content.lower()
        assert "pip install --no-cache-dir uv==" not in content


def test_release_buildspec_requires_buildkit() -> None:
    """Assert the release buildspec requires BuildKit for Docker builds."""
    content = _RELEASE_BUILDSPEC.read_text(encoding="utf-8")
    assert 'DOCKER_BUILDKIT: "1"' in content
    assert "DOCKER_BUILDKIT" in content


def test_service_packages_declare_runtime_support_dependency() -> None:
    """Assert service packages declare nova-runtime-support>=0.1.0."""
    package_paths = (
        REPO_ROOT / "packages" / "nova_file_api" / "pyproject.toml",
    )

    for package_path in package_paths:
        payload = tomllib.loads(package_path.read_text(encoding="utf-8"))
        dependencies = payload["project"]["dependencies"]
        assert "nova-runtime-support>=0.1.0" in dependencies


def test_async_template_enforces_dlq_redrive_and_retention_safety() -> None:
    content = _ASYNC_TEMPLATE.read_text(encoding="utf-8")

    assert "JobsDeadLetterQueue:" in content
    assert "MessageRetentionPeriod: 1209600" in content
    assert "JobsMessageRetentionSeconds:" in content
    assert "MaxValue: 1209599" in content

    assert "RedrivePolicy:" in content
    assert "deadLetterTargetArn: !GetAtt JobsDeadLetterQueue.Arn" in content
    assert "maxReceiveCount: !Ref JobsMaxReceiveCount" in content
