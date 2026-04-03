"""Tests for release execution manifest generation."""

from __future__ import annotations

from pathlib import Path

from scripts.release.write_execution_manifest import build_execution_manifest


def test_build_execution_manifest_includes_required_release_fields() -> None:
    payload = build_execution_manifest(
        repo_root=Path("repo-root"),
        release_commit_sha="abc123",
        api_lambda_artifact={
            "artifact_bucket": "release-artifacts",
            "artifact_key": (
                "runtime/nova-file-api/abc123/sha/nova-file-api-lambda.zip"
            ),
            "artifact_sha256": "f" * 64,
        },
        workflow_lambda_artifact={
            "artifact_bucket": "release-artifacts",
            "artifact_key": (
                "runtime/nova-workflows/abc123/sha/nova-workflows-lambda.zip"
            ),
            "artifact_sha256": "e" * 64,
        },
        release_prep_payload={
            "changed_units": [{"unit_id": "packages/nova_file_api"}],
            "units": [
                {
                    "unit_id": "packages/nova_file_api",
                    "new_version": "0.1.1",
                }
            ],
        },
        manifest_sha256="a" * 64,
        manifest_bucket="release-manifests",
        manifest_key="releases/abc123/release-execution-manifest.json",
        staging_repository="nova-staging",
        prod_repository="nova-prod",
    )

    assert payload["release_commit_sha"] == "abc123"
    assert payload["release_manifest_sha256"] == "a" * 64
    assert payload["release_manifest_bucket"] == "release-manifests"
    assert payload["api_lambda_artifact"]["artifact_sha256"] == "f" * 64
    assert payload["workflow_lambda_artifact"]["artifact_sha256"] == "e" * 64
    assert payload["release_prep"]["units"][0]["new_version"] == "0.1.1"
    assert payload["codeartifact"]["staging_repository"] == "nova-staging"
    assert payload["codeartifact"]["prod_repository"] == "nova-prod"
