"""Tests for release execution manifest generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release.write_execution_manifest import (
    _validate_commit_matches,
    build_execution_manifest,
)


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


def test_validate_commit_matches_accepts_matching_commit_field() -> None:
    _validate_commit_matches(
        expected="abc123",
        payload={"release_commit_sha": "abc123"},
        source="api_lambda_artifact",
    )


def test_validate_commit_matches_rejects_mismatched_commit() -> None:
    with pytest.raises(ValueError, match="commit mismatch"):
        _validate_commit_matches(
            expected="abc123",
            payload={"release_commit_sha": "def456"},
            source="api_lambda_artifact",
        )


def test_validate_commit_matches_skips_when_commit_field_is_absent() -> None:
    _validate_commit_matches(
        expected="abc123",
        payload={},
        source="release_prep_payload",
    )


def test_validate_commit_matches_checks_release_prep_commit_field() -> None:
    with pytest.raises(ValueError, match="commit mismatch"):
        _validate_commit_matches(
            expected="abc123",
            payload={"commit": "def456"},
            source="release_prep_payload",
            commit_key="commit",
        )
