"""Write one machine-readable release execution manifest."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from scripts.release import common, release_paths


def build_execution_manifest(
    *,
    repo_root: Path,
    release_commit_sha: str,
    api_lambda_artifact: dict[str, Any],
    workflow_lambda_artifact: dict[str, Any],
    release_prep_payload: dict[str, Any],
    manifest_sha256: str,
    manifest_bucket: str,
    manifest_key: str,
    staging_repository: str,
    prod_repository: str,
) -> dict[str, Any]:
    """Return the canonical release execution manifest payload.

    Args:
        repo_root: Absolute repository root used for execution context.
        release_commit_sha: Release commit SHA pinned by the release pipeline.
        api_lambda_artifact: Normalized API Lambda artifact metadata payload.
        workflow_lambda_artifact: Normalized workflow Lambda artifact metadata
            payload.
        release_prep_payload: Canonical release prep payload.
        manifest_sha256: SHA256 digest of the release version manifest.
        manifest_bucket: Destination S3 bucket for release manifest artifacts.
        manifest_key: Destination S3 object key for the manifest.
        staging_repository: Staging CodeArtifact repository name.
        prod_repository: Production CodeArtifact repository name.

    Returns:
        Canonical release execution manifest payload.
    """
    return {
        "schema_version": "1.0",
        "generated_at": common.iso_timestamp(),
        "release_commit_sha": release_commit_sha,
        "release_manifest_path": release_paths.RELEASE_VERSION_MANIFEST_PATH,
        "release_manifest_sha256": manifest_sha256,
        "release_manifest_bucket": manifest_bucket,
        "release_manifest_key": manifest_key,
        "release_prep": release_prep_payload,
        "api_lambda_artifact": api_lambda_artifact,
        "workflow_lambda_artifact": workflow_lambda_artifact,
        "codeartifact": {
            "staging_repository": staging_repository,
            "prod_repository": prod_repository,
        },
        "repo_root": str(repo_root),
    }


def _validate_commit_matches(
    *,
    expected: str,
    payload: dict[str, Any],
    source: str,
    commit_key: str = "release_commit_sha",
) -> None:
    if commit_key not in payload:
        return
    actual = payload[commit_key]
    if not isinstance(actual, str):
        raise TypeError(
            f"{source} payload field {commit_key!r} must be a string commit SHA"
        )
    if actual.lower() != expected.lower():
        raise ValueError(
            f"{source} commit mismatch: {commit_key}={actual} does not match "
            f"--release-commit-sha={expected}"
        )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for execution manifest generation.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--release-commit-sha", required=True)
    parser.add_argument("--api-lambda-artifact-path", required=True)
    parser.add_argument("--workflow-lambda-artifact-path", required=True)
    parser.add_argument(
        "--release-prep-path",
        default=release_paths.RELEASE_PREP_PATH,
    )
    parser.add_argument(
        "--release-manifest-path",
        default=release_paths.RELEASE_VERSION_MANIFEST_PATH,
    )
    parser.add_argument("--release-manifest-bucket", required=True)
    parser.add_argument("--release-manifest-key", required=True)
    parser.add_argument("--staging-repository", required=True)
    parser.add_argument("--prod-repository", required=True)
    parser.add_argument(
        "--output-path",
        default=release_paths.RELEASE_EXECUTION_MANIFEST_PATH,
    )
    return parser.parse_args()


def main() -> int:
    """Render and write the execution manifest.

    Returns:
        Process exit code where 0 means success.
    """
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    api_lambda_artifact_path = Path(args.api_lambda_artifact_path)
    if not api_lambda_artifact_path.is_absolute():
        api_lambda_artifact_path = repo_root / api_lambda_artifact_path
    workflow_lambda_artifact_path = Path(args.workflow_lambda_artifact_path)
    if not workflow_lambda_artifact_path.is_absolute():
        workflow_lambda_artifact_path = (
            repo_root / workflow_lambda_artifact_path
        )
    release_prep_path = Path(args.release_prep_path)
    if not release_prep_path.is_absolute():
        release_prep_path = repo_root / release_prep_path
    release_manifest_path = Path(args.release_manifest_path)
    if not release_manifest_path.is_absolute():
        release_manifest_path = repo_root / release_manifest_path
    output_path = Path(args.output_path)
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    api_lambda_artifact = common.read_json(api_lambda_artifact_path)
    workflow_lambda_artifact = common.read_json(workflow_lambda_artifact_path)
    release_prep_payload = common.read_json(release_prep_path)

    _validate_commit_matches(
        expected=args.release_commit_sha,
        payload=api_lambda_artifact,
        source="api_lambda_artifact",
    )
    _validate_commit_matches(
        expected=args.release_commit_sha,
        payload=workflow_lambda_artifact,
        source="workflow_lambda_artifact",
    )
    _validate_commit_matches(
        expected=args.release_commit_sha,
        payload=release_prep_payload,
        source="release_prep_payload",
        commit_key="commit",
    )

    manifest_sha256 = hashlib.sha256(
        release_manifest_path.read_bytes()
    ).hexdigest()

    payload = build_execution_manifest(
        repo_root=repo_root,
        release_commit_sha=args.release_commit_sha,
        api_lambda_artifact=api_lambda_artifact,
        workflow_lambda_artifact=workflow_lambda_artifact,
        release_prep_payload=release_prep_payload,
        manifest_sha256=manifest_sha256,
        manifest_bucket=args.release_manifest_bucket,
        manifest_key=args.release_manifest_key,
        staging_repository=args.staging_repository,
        prod_repository=args.prod_repository,
    )
    common.write_json(output_path, payload)
    print(f"execution-manifest written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
