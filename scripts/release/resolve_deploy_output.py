#!/usr/bin/env python3
"""Build and resolve authoritative runtime deploy-output artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.release import common

_REQUIRED_API_LAMBDA_FIELDS = (
    "artifact_bucket",
    "artifact_key",
    "artifact_sha256",
    "package_name",
    "package_version",
    "release_commit_sha",
)
_REQUIRED_DEPLOY_OUTPUT_FIELDS = (
    "schema_version",
    "captured_at",
    "repository",
    "deploy_run_id",
    "deploy_run_attempt",
    "deploy_workflow_ref",
    "stack_name",
    "region",
    "environment",
    "runtime_name",
    "runtime_version",
    "release_commit_sha",
    "public_base_url",
    "stack_outputs",
    "api_lambda_artifact",
)


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON object.

    Raises:
        TypeError: If the JSON root is not an object.
    """
    return common.read_json(path)


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Return canonical JSON bytes for a deploy-output payload."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_hex(payload: dict[str, Any]) -> str:
    """Return the SHA256 digest for a deploy-output payload."""
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _read_expected_sha256(path: Path) -> str:
    """Read a SHA256 sidecar file written in ``sha256sum`` format."""
    digest = path.read_text(encoding="utf-8").strip().split()[0]
    if not digest or len(digest) != 64:
        raise ValueError(f"Invalid SHA256 digest sidecar: {path}")
    return digest.lower()


def _normalize_stack_outputs(
    stack_description: dict[str, Any],
) -> dict[str, str]:
    """Extract normalized stack outputs from a CloudFormation description."""
    raw_outputs = stack_description.get("Outputs")
    if not isinstance(raw_outputs, list) or not raw_outputs:
        raise TypeError(
            "Stack description must contain a non-empty Outputs list"
        )

    outputs: dict[str, str] = {}
    for output in raw_outputs:
        if not isinstance(output, dict):
            raise TypeError("Each CloudFormation output must be an object")
        export_name = output.get("ExportName")
        key = (
            export_name
            if isinstance(export_name, str)
            else output.get("OutputKey")
        )
        value = output.get("OutputValue")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("CDK output keys must be non-empty strings")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "CloudFormation output "
                f"{key!r} must resolve to a non-empty string"
            )
        outputs[key.strip()] = value.strip()
    return outputs


def _normalize_api_lambda_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the immutable API Lambda artifact manifest payload."""
    missing = [
        field_name
        for field_name in _REQUIRED_API_LAMBDA_FIELDS
        if not isinstance(payload.get(field_name), str)
        or not str(payload[field_name]).strip()
    ]
    if missing:
        raise ValueError(
            "API Lambda artifact manifest is missing required fields: "
            + ", ".join(missing)
        )
    artifact_sha256 = str(payload["artifact_sha256"]).strip().lower()
    if len(artifact_sha256) != 64:
        raise ValueError("artifact_sha256 must be a 64-character digest")

    normalized = dict(payload)
    normalized["artifact_sha256"] = artifact_sha256
    return normalized


def build_deploy_output(
    *,
    api_lambda_artifact: dict[str, Any],
    stack_name: str,
    region: str,
    environment_name: str,
    repository: str,
    deploy_run_id: int,
    deploy_run_attempt: int,
    deploy_workflow_ref: str,
    stack_description: dict[str, Any],
) -> dict[str, Any]:
    """Construct a normalized deploy-output authority payload."""
    normalized_artifact = _normalize_api_lambda_artifact(api_lambda_artifact)
    outputs = _normalize_stack_outputs(stack_description)
    public_base_url = outputs.get("NovaPublicBaseUrl", "").strip()
    if not public_base_url.startswith("https://"):
        raise ValueError(
            "NovaPublicBaseUrl output must be an HTTPS URL in deploy output"
        )

    deploy_output: dict[str, Any] = {
        "schema_version": "2.0",
        "captured_at": datetime.now(UTC).isoformat(),
        "repository": repository,
        "deploy_run_id": deploy_run_id,
        "deploy_run_attempt": deploy_run_attempt,
        "deploy_workflow_ref": deploy_workflow_ref,
        "stack_name": stack_name,
        "region": region,
        "environment": environment_name,
        "runtime_name": normalized_artifact["package_name"],
        "runtime_version": normalized_artifact["package_version"],
        "release_commit_sha": normalized_artifact["release_commit_sha"],
        "public_base_url": public_base_url,
        "stack_outputs": outputs,
        "api_lambda_artifact": normalized_artifact,
    }
    stack_id = stack_description.get("StackId")
    if isinstance(stack_id, str) and stack_id.strip():
        deploy_output["stack_id"] = stack_id.strip()
    return deploy_output


def load_deploy_output(
    *,
    deploy_output_path: Path,
    sha256_path: Path | None = None,
) -> tuple[dict[str, Any], str]:
    """Load and validate a deploy-output artifact.

    Args:
        deploy_output_path: Path to ``deploy-output.json``.
        sha256_path: Optional sidecar path containing an expected digest.

    Returns:
        Tuple of ``(payload, sha256_digest)``.

    Raises:
        ValueError: If the deploy-output payload is malformed or the digest
            check fails.
    """
    payload = _load_json_object(deploy_output_path)
    missing = [
        field_name
        for field_name in _REQUIRED_DEPLOY_OUTPUT_FIELDS
        if field_name not in payload
    ]
    if missing:
        raise ValueError(
            "Deploy output is missing required fields: " + ", ".join(missing)
        )

    if payload["schema_version"] != "2.0":
        raise ValueError("Deploy output schema_version must be 2.0")

    public_base_url = payload.get("public_base_url")
    if not isinstance(public_base_url, str) or not public_base_url.startswith(
        "https://"
    ):
        raise ValueError("public_base_url must be an HTTPS URL")

    runtime_version = payload.get("runtime_version")
    if not isinstance(runtime_version, str) or not runtime_version.strip():
        raise ValueError("runtime_version must be a non-empty string")

    stack_outputs = payload.get("stack_outputs")
    if not isinstance(stack_outputs, dict) or not stack_outputs:
        raise ValueError("stack_outputs must be a non-empty object")

    if stack_outputs.get("NovaPublicBaseUrl") != public_base_url:
        raise ValueError(
            "stack_outputs.NovaPublicBaseUrl must match public_base_url"
        )

    api_lambda_artifact = payload.get("api_lambda_artifact")
    if not isinstance(api_lambda_artifact, dict):
        raise TypeError("api_lambda_artifact must be an object")
    _normalize_api_lambda_artifact(api_lambda_artifact)

    actual_digest = _sha256_hex(payload)
    if sha256_path is not None:
        expected_digest = _read_expected_sha256(sha256_path)
        if actual_digest != expected_digest:
            raise ValueError(
                "deploy-output digest mismatch: "
                f"expected {expected_digest}, got {actual_digest}"
            )
    return payload, actual_digest


def _append_github_outputs(path: Path, outputs: dict[str, str]) -> None:
    """Append key/value outputs to a GitHub Actions output file."""
    with path.open("a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build or resolve authoritative runtime deploy output."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser(
        "build",
        help="Build deploy-output.json from release and deploy artifacts.",
    )
    build.add_argument("--api-lambda-artifact-path", required=True)
    build.add_argument("--stack-name", required=True)
    build.add_argument("--region", required=True)
    build.add_argument("--environment-name", required=True)
    build.add_argument("--repository", required=True)
    build.add_argument("--deploy-run-id", required=True, type=int)
    build.add_argument("--deploy-run-attempt", required=True, type=int)
    build.add_argument("--deploy-workflow-ref", required=True)
    build.add_argument("--stack-description-path", required=True)
    build.add_argument("--output-path", required=True)
    build.add_argument("--sha256-path", required=True)

    emit = subparsers.add_parser(
        "emit",
        help="Resolve deploy-output.json and emit workflow-friendly fields.",
    )
    emit.add_argument("--deploy-output-path", required=True)
    emit.add_argument("--sha256-path")
    emit.add_argument("--github-output-path")

    return parser.parse_args()


def _run_build(args: argparse.Namespace) -> int:
    """Handle the ``build`` command."""
    api_lambda_artifact = _load_json_object(
        Path(args.api_lambda_artifact_path).resolve()
    )
    stack_description = _load_json_object(
        Path(args.stack_description_path).resolve()
    )

    deploy_output = build_deploy_output(
        api_lambda_artifact=api_lambda_artifact,
        stack_name=args.stack_name,
        region=args.region,
        environment_name=args.environment_name,
        repository=args.repository,
        deploy_run_id=args.deploy_run_id,
        deploy_run_attempt=args.deploy_run_attempt,
        deploy_workflow_ref=args.deploy_workflow_ref,
        stack_description=stack_description,
    )
    output_path = Path(args.output_path).resolve()
    sha256_path = Path(args.sha256_path).resolve()
    common.write_json(output_path, deploy_output)
    sha256_path.parent.mkdir(parents=True, exist_ok=True)
    sha256_path.write_text(
        f"{_sha256_hex(deploy_output)}  {output_path.name}\n",
        encoding="utf-8",
    )
    return 0


def _run_emit(args: argparse.Namespace) -> int:
    """Handle the ``emit`` command."""
    payload, actual_digest = load_deploy_output(
        deploy_output_path=Path(args.deploy_output_path).resolve(),
        sha256_path=(
            Path(args.sha256_path).resolve() if args.sha256_path else None
        ),
    )
    outputs = {
        "deploy_output_sha256": actual_digest,
        "public_base_url": str(payload["public_base_url"]),
        "runtime_name": str(payload["runtime_name"]),
        "runtime_version": str(payload["runtime_version"]),
        "release_commit_sha": str(payload["release_commit_sha"]),
        "stack_name": str(payload["stack_name"]),
        "region": str(payload["region"]),
    }
    for key, value in outputs.items():
        print(f"{key}={value}")
    if args.github_output_path:
        _append_github_outputs(Path(args.github_output_path), outputs)
    return 0


def main() -> int:
    """Run the deploy-output resolution CLI."""
    args = _parse_args()
    if args.command == "build":
        return _run_build(args)
    return _run_emit(args)


if __name__ == "__main__":
    raise SystemExit(main())
