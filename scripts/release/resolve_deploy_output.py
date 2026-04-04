#!/usr/bin/env python3
"""Build and resolve authoritative runtime deploy-output artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
    "execution",
    "stack_name",
    "region",
    "environment",
    "runtime_name",
    "runtime_version",
    "release_commit_sha",
    "public_base_url",
    "execute_api_endpoint",
    "cors_allowed_origins",
    "stack_outputs",
    "api_lambda_artifact",
    "workflow_lambda_artifact",
)
_AUTHORITATIVE_STACK_OUTPUT_KEYS = (
    "NovaAlarmTopicArn",
    "NovaApiAccessLogGroupName",
    "NovaExportCopyPartsTableName",
    "NovaExportWorkflowStateMachineArn",
    "NovaExportsTableName",
    "NovaIdempotencyTableName",
    "NovaObservabilityDashboardName",
    "NovaPublicBaseUrl",
    "NovaRestApiEndpoint",
    "NovaStorageLensConfigurationId",
    "NovaTransferPolicyAppConfigApplicationId",
    "NovaTransferPolicyAppConfigEnvironmentId",
    "NovaTransferPolicyAppConfigProfileId",
    "NovaTransferSpendBudgetName",
    "NovaTransferUsageTableName",
    "NovaUploadSessionsTableName",
    "NovaWafLogGroupName",
)


def _canonical_output_key(raw_key: str) -> str:
    """Normalize CloudFormation output names into authority keys."""
    key = raw_key.strip()
    if key.startswith("ExportNova"):
        return key.removeprefix("Export")
    if key.startswith("NovaRestApiEndpoint"):
        return "NovaRestApiEndpoint"
    if key.startswith("NovaDev"):
        return "Nova" + key.removeprefix("NovaDev")
    if key.startswith("NovaProd"):
        return "Nova" + key.removeprefix("NovaProd")
    return key


def _validate_allowed_origin(entry: object) -> str:
    """Validate one allowed origin token and return the normalized string."""
    if not isinstance(entry, str):
        raise TypeError(f"invalid allowed_origin: {entry}")

    origin = entry.strip()
    if origin == "*":
        return origin

    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"invalid allowed_origin: {entry}")
    return origin


def _normalize_allowed_origins(
    *,
    raw_value: str,
    environment_name: str,
) -> list[str]:
    """Normalize deploy-time CORS origins into the emitted authority list."""
    stripped = raw_value.strip()
    if not stripped:
        if environment_name.lower() == "prod":
            raise ValueError(
                "allowed_origins must be configured for production "
                "deploy output"
            )
        return ["*"]

    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"allowed_origins JSON is malformed: {exc}"
            ) from exc
        if not isinstance(parsed, list):
            raise TypeError("allowed_origins JSON input must decode to a list")
        origins = []
        for origin in parsed:
            if isinstance(origin, str) and not origin.strip():
                continue
            origins.append(_validate_allowed_origin(origin))
    else:
        origins = [
            _validate_allowed_origin(origin)
            for origin in (part.strip() for part in stripped.split(","))
            if origin
        ]
    if not origins:
        raise ValueError("allowed_origins resolved to an empty list")
    return origins


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
        output_key = output.get("OutputKey")
        export_name = output.get("ExportName")
        key_candidates = []
        if isinstance(output_key, str) and output_key.strip():
            key_candidates.append(output_key)
        if isinstance(export_name, str) and export_name.strip():
            key_candidates.append(export_name)
        value = output.get("OutputValue")
        if not key_candidates:
            raise ValueError("CDK output keys must be non-empty strings")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "CloudFormation output must resolve to a non-empty string"
            )
        canonical_key = next(
            (
                normalized_key
                for normalized_key in (
                    _canonical_output_key(candidate)
                    for candidate in key_candidates
                )
                if normalized_key in _AUTHORITATIVE_STACK_OUTPUT_KEYS
            ),
            _canonical_output_key(key_candidates[0]),
        )
        if canonical_key not in _AUTHORITATIVE_STACK_OUTPUT_KEYS:
            continue
        normalized_value = value.strip()
        if canonical_key == "NovaRestApiEndpoint":
            normalized_value = normalized_value.rstrip("/")
        outputs[canonical_key] = normalized_value
    if "NovaPublicBaseUrl" not in outputs:
        raise ValueError(
            "CloudFormation outputs must include NovaPublicBaseUrl"
        )
    return outputs


def _execute_api_endpoint_from_outputs(outputs: dict[str, str]) -> str:
    """Return the disabled default execute-api endpoint from stack outputs."""
    endpoint = outputs.get("NovaRestApiEndpoint", "").strip()
    if not endpoint.startswith("https://") or ".execute-api." not in endpoint:
        raise ValueError(
            "CloudFormation outputs must include NovaRestApiEndpoint"
        )
    return endpoint.rstrip("/")


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

    normalized = {
        field_name: str(payload[field_name]).strip()
        for field_name in _REQUIRED_API_LAMBDA_FIELDS
    }
    normalized["artifact_sha256"] = artifact_sha256
    return normalized


def _validate_release_commit_alignment(
    *,
    release_commit_sha: str,
    api_lambda_artifact: dict[str, Any],
    workflow_lambda_artifact: dict[str, Any],
) -> None:
    """Assert release commit alignment across top-level/runtime artifacts."""
    api_release_commit = str(api_lambda_artifact["release_commit_sha"]).strip()
    workflow_release_commit = str(
        workflow_lambda_artifact["release_commit_sha"]
    ).strip()
    if api_release_commit != release_commit_sha:
        raise ValueError(
            "api_lambda_artifact.release_commit_sha must match "
            "release_commit_sha"
        )
    if workflow_release_commit != release_commit_sha:
        raise ValueError(
            "workflow_lambda_artifact.release_commit_sha must match "
            "release_commit_sha"
        )
    if workflow_release_commit != api_release_commit:
        raise ValueError(
            "workflow_lambda_artifact.release_commit_sha must match "
            "api_lambda_artifact.release_commit_sha"
        )


def build_deploy_output(
    *,
    api_lambda_artifact: dict[str, Any],
    workflow_lambda_artifact: dict[str, Any],
    stack_name: str,
    region: str,
    environment_name: str,
    allowed_origins: str,
    repository: str,
    pipeline_name: str,
    pipeline_execution_id: str,
    codebuild_build_ids: list[str],
    stack_description: dict[str, Any],
) -> dict[str, Any]:
    """Construct a normalized deploy-output authority payload."""
    normalized_artifact = _normalize_api_lambda_artifact(api_lambda_artifact)
    normalized_workflow_artifact = _normalize_api_lambda_artifact(
        workflow_lambda_artifact
    )
    release_commit_sha = str(normalized_artifact["release_commit_sha"]).strip()
    _validate_release_commit_alignment(
        release_commit_sha=release_commit_sha,
        api_lambda_artifact=normalized_artifact,
        workflow_lambda_artifact=normalized_workflow_artifact,
    )
    outputs = _normalize_stack_outputs(stack_description)
    public_base_url = outputs.get("NovaPublicBaseUrl", "").strip()
    if not public_base_url.startswith("https://"):
        raise ValueError(
            "NovaPublicBaseUrl output must be an HTTPS URL in deploy output"
        )
    execute_api_endpoint = _execute_api_endpoint_from_outputs(outputs)
    cors_allowed_origins = _normalize_allowed_origins(
        raw_value=allowed_origins,
        environment_name=environment_name,
    )
    normalized_build_ids = [
        item.strip() for item in codebuild_build_ids if item.strip()
    ]
    if not normalized_build_ids:
        raise ValueError(
            "codebuild_build_ids must include at least one build id"
        )
    normalized_pipeline_name = pipeline_name.strip()
    normalized_pipeline_execution_id = pipeline_execution_id.strip()
    if not normalized_pipeline_name or not normalized_pipeline_execution_id:
        raise ValueError(
            "pipeline_name and pipeline_execution_id must be non-empty strings"
        )

    deploy_output: dict[str, Any] = {
        "schema_version": "2.0",
        "captured_at": datetime.now(UTC).isoformat(),
        "repository": repository,
        "execution": {
            "system": "aws-codepipeline",
            "pipeline_name": normalized_pipeline_name,
            "pipeline_execution_id": normalized_pipeline_execution_id,
            "codebuild_build_ids": normalized_build_ids,
        },
        "stack_name": stack_name,
        "region": region,
        "environment": environment_name,
        "runtime_name": normalized_artifact["package_name"],
        "runtime_version": normalized_artifact["package_version"],
        "release_commit_sha": release_commit_sha,
        "public_base_url": public_base_url,
        "execute_api_endpoint": execute_api_endpoint,
        "cors_allowed_origins": cors_allowed_origins,
        "stack_outputs": outputs,
        "api_lambda_artifact": normalized_artifact,
        "workflow_lambda_artifact": normalized_workflow_artifact,
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
    execute_api_endpoint = payload.get("execute_api_endpoint")
    if (
        not isinstance(execute_api_endpoint, str)
        or not execute_api_endpoint.startswith("https://")
        or ".execute-api." not in execute_api_endpoint
    ):
        raise ValueError(
            "execute_api_endpoint must be an HTTPS execute-api URL"
        )
    cors_allowed_origins = payload.get("cors_allowed_origins")
    if (
        not isinstance(cors_allowed_origins, list)
        or not cors_allowed_origins
        or any(
            not isinstance(origin, str) or not origin.strip()
            for origin in cors_allowed_origins
        )
    ):
        raise ValueError(
            "cors_allowed_origins must be a non-empty list of strings"
        )

    runtime_version = payload.get("runtime_version")
    if not isinstance(runtime_version, str) or not runtime_version.strip():
        raise ValueError("runtime_version must be a non-empty string")
    release_commit_sha = payload.get("release_commit_sha")
    if (
        not isinstance(release_commit_sha, str)
        or not release_commit_sha.strip()
    ):
        raise ValueError("release_commit_sha must be a non-empty string")

    stack_outputs = payload.get("stack_outputs")
    if not isinstance(stack_outputs, dict) or not stack_outputs:
        raise ValueError("stack_outputs must be a non-empty object")
    unknown_output_keys = sorted(
        set(stack_outputs) - set(_AUTHORITATIVE_STACK_OUTPUT_KEYS)
    )
    if unknown_output_keys:
        raise ValueError(
            "stack_outputs contains non-authoritative keys: "
            + ", ".join(unknown_output_keys)
        )

    if stack_outputs.get("NovaPublicBaseUrl") != public_base_url:
        raise ValueError(
            "stack_outputs.NovaPublicBaseUrl must match public_base_url"
        )
    if stack_outputs.get("NovaRestApiEndpoint") != execute_api_endpoint:
        raise ValueError(
            "stack_outputs.NovaRestApiEndpoint must match execute_api_endpoint"
        )

    api_lambda_artifact = payload.get("api_lambda_artifact")
    if not isinstance(api_lambda_artifact, dict):
        raise TypeError("api_lambda_artifact must be an object")
    normalized_api_lambda_artifact = _normalize_api_lambda_artifact(
        api_lambda_artifact
    )
    workflow_lambda_artifact = payload.get("workflow_lambda_artifact")
    if not isinstance(workflow_lambda_artifact, dict):
        raise TypeError("workflow_lambda_artifact must be an object")
    normalized_workflow_lambda_artifact = _normalize_api_lambda_artifact(
        workflow_lambda_artifact
    )
    _validate_release_commit_alignment(
        release_commit_sha=release_commit_sha.strip(),
        api_lambda_artifact=normalized_api_lambda_artifact,
        workflow_lambda_artifact=normalized_workflow_lambda_artifact,
    )

    execution = payload.get("execution")
    if not isinstance(execution, dict):
        raise TypeError("execution must be an object")
    if execution.get("system") != "aws-codepipeline":
        raise ValueError("execution.system must be aws-codepipeline")
    for key in ("pipeline_name", "pipeline_execution_id"):
        value = execution.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"execution.{key} must be a non-empty string")
    build_ids = execution.get("codebuild_build_ids")
    if (
        not isinstance(build_ids, list)
        or not build_ids
        or any(
            not isinstance(value, str) or not value.strip()
            for value in build_ids
        )
    ):
        raise ValueError(
            "execution.codebuild_build_ids must be a non-empty list of strings"
        )
    if any(
        not isinstance(value, str) or not value.strip() for value in build_ids
    ):
        raise ValueError(
            "execution.codebuild_build_ids must be a non-empty list of strings"
        )

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
    build.add_argument("--workflow-lambda-artifact-path", required=True)
    build.add_argument("--stack-name", required=True)
    build.add_argument("--region", required=True)
    build.add_argument("--environment-name", required=True)
    build.add_argument("--allowed-origins", required=False, default="")
    build.add_argument("--repository", required=True)
    build.add_argument("--pipeline-name", required=True)
    build.add_argument("--pipeline-execution-id", required=True)
    build.add_argument("--codebuild-build-id", action="append", default=[])
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
    workflow_lambda_artifact = _load_json_object(
        Path(args.workflow_lambda_artifact_path).resolve()
    )
    stack_description = _load_json_object(
        Path(args.stack_description_path).resolve()
    )

    deploy_output = build_deploy_output(
        api_lambda_artifact=api_lambda_artifact,
        workflow_lambda_artifact=workflow_lambda_artifact,
        stack_name=args.stack_name,
        region=args.region,
        environment_name=args.environment_name,
        allowed_origins=args.allowed_origins,
        repository=args.repository,
        pipeline_name=args.pipeline_name,
        pipeline_execution_id=args.pipeline_execution_id,
        codebuild_build_ids=args.codebuild_build_id,
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
