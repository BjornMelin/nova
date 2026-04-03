"""Contract tests for the CDK app entrypoint stack selection logic."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from .helpers import REPO_ROOT, runtime_stack_context_for_region


def _release_control_env() -> dict[str, str]:
    return {
        "RELEASE_GITHUB_OWNER": "BjornMelin",
        "RELEASE_GITHUB_REPO": "nova",
        "RELEASE_CONNECTION_ARN": (
            "arn:aws:codeconnections:us-east-1:111111111111:"
            "connection/12345678-1234-1234-1234-123456789012"
        ),
        "CODEARTIFACT_DOMAIN": "nova-internal",
        "CODEARTIFACT_STAGING_REPOSITORY": "nova-staging",
        "CODEARTIFACT_PROD_REPOSITORY": "nova-prod",
        "RELEASE_SIGNING_SECRET_ID": "nova/release/signing",
        "DEV_RUNTIME_CONFIG_PARAMETER_NAME": "/nova/release/runtime-config/dev",
        "PROD_RUNTIME_CONFIG_PARAMETER_NAME": (
            "/nova/release/runtime-config/prod"
        ),
    }


def _run_app(
    tmp_path: Path,
    *,
    extra_env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    outdir = tmp_path / "cdk.out"
    env = {
        **os.environ,
        "CDK_DEFAULT_ACCOUNT": "111111111111",
        "CDK_DEFAULT_REGION": "us-east-1",
        "CDK_OUTDIR": str(outdir),
        **extra_env,
    }
    return subprocess.run(  # noqa: S603
        [sys.executable, str(REPO_ROOT / "infra/nova_cdk/app.py")],
        check=False,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )


def _artifact_ids(tmp_path: Path) -> set[str]:
    manifest_path = tmp_path / "cdk.out" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return set(manifest.get("artifacts", {}))


def test_release_only_inputs_synthesize_release_stacks_without_runtime_inputs(
    tmp_path: Path,
) -> None:
    result = _run_app(tmp_path, extra_env=_release_control_env())

    assert result.returncode == 0, result.stderr
    artifact_ids = _artifact_ids(tmp_path)
    assert "NovaRuntimeStack" not in artifact_ids
    assert "NovaReleaseControlPlaneStack" in artifact_ids
    assert "NovaReleaseSupportStack" in artifact_ids


def test_runtime_only_inputs_synthesize_runtime_stack(tmp_path: Path) -> None:
    result = _run_app(
        tmp_path,
        extra_env={
            env_var.upper(): value
            for env_var, value in runtime_stack_context_for_region(
                "us-east-1"
            ).items()
        },
    )

    assert result.returncode == 0, result.stderr
    artifact_ids = _artifact_ids(tmp_path)
    assert "NovaRuntimeStack" in artifact_ids
    assert "NovaReleaseControlPlaneStack" not in artifact_ids


def test_combined_inputs_synthesize_runtime_and_release_stacks(
    tmp_path: Path,
) -> None:
    runtime_env = {
        env_var.upper(): value
        for env_var, value in runtime_stack_context_for_region(
            "us-east-1"
        ).items()
    }
    result = _run_app(
        tmp_path,
        extra_env={**runtime_env, **_release_control_env()},
    )

    assert result.returncode == 0, result.stderr
    artifact_ids = _artifact_ids(tmp_path)
    assert "NovaRuntimeStack" in artifact_ids
    assert "NovaReleaseControlPlaneStack" in artifact_ids
    assert "NovaReleaseSupportStack" in artifact_ids


def test_app_requires_runtime_or_release_inputs(tmp_path: Path) -> None:
    result = _run_app(tmp_path, extra_env={})

    assert result.returncode != 0
    assert "Provide runtime stack inputs or release-control inputs" in (
        result.stderr
    )
