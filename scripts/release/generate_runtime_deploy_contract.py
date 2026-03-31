#!/usr/bin/env python3
"""Generate runtime deploy workflow and deploy-output contract schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.release import common

_SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"
_CONTRACTS_DIR = Path("docs/contracts")
_DEPLOY_OUTPUT_PATH = _CONTRACTS_DIR / "deploy-output-authority-v2.schema.json"
_WORKFLOW_SCHEMA_PATH = (
    _CONTRACTS_DIR / "workflow-deploy-runtime-v1.schema.json"
)
_STACK_OUTPUT_PROPERTIES: dict[str, dict[str, object]] = {
    "NovaAlarmTopicArn": {
        "type": "string",
        "pattern": "^arn:aws:sns:[a-z0-9-]+:\\d{12}:.+$",
    },
    "NovaApiAccessLogGroupName": {
        "type": "string",
        "pattern": "^/aws/apigateway/.+$",
    },
    "NovaExportWorkflowStateMachineArn": {
        "type": "string",
        "pattern": "^arn:aws:states:[a-z0-9-]+:\\d{12}:stateMachine:.+$",
    },
    "NovaExportsTableName": {
        "type": "string",
        "minLength": 1,
    },
    "NovaIdempotencyTableName": {
        "type": "string",
        "minLength": 1,
    },
    "NovaPublicBaseUrl": {
        "type": "string",
        "pattern": "^https://.+$",
    },
    "NovaRestApiEndpoint": {
        "type": "string",
        "pattern": "^https://.+\\.execute-api\\..+$",
    },
    "NovaWafLogGroupName": {
        "type": "string",
        "pattern": "^aws-waf-logs-.+$",
    },
}


def build_deploy_output_schema() -> dict[str, Any]:
    """Return the deploy-output authority schema."""
    return {
        "$schema": _SCHEMA_URI,
        "$id": (
            "https://3m-cloud.github.io/nova/docs/contracts/"
            "deploy-output-authority-v2.schema.json"
        ),
        "title": "Runtime deploy-output authority",
        "description": (
            "Authoritative runtime deployment artifact emitted by the "
            "deploy-runtime workflow."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": [
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
            "execute_api_endpoint",
            "cors_allowed_origins",
            "stack_outputs",
            "api_lambda_artifact",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": "2.0"},
            "captured_at": {"type": "string", "format": "date-time"},
            "repository": {
                "type": "string",
                "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
            },
            "deploy_run_id": {"type": "integer", "minimum": 1},
            "deploy_run_attempt": {"type": "integer", "minimum": 1},
            "deploy_workflow_ref": {"type": "string", "minLength": 1},
            "stack_name": {"type": "string", "minLength": 1},
            "stack_id": {
                "type": "string",
                "pattern": (
                    "^arn:aws:cloudformation:[a-z0-9-]+:\\d{12}:stack/.+$"
                ),
            },
            "region": {"type": "string", "pattern": "^[a-z]{2}-[a-z]+-\\d+$"},
            "environment": {"type": "string", "minLength": 1},
            "runtime_name": {"type": "string", "minLength": 1},
            "runtime_version": {"type": "string", "minLength": 1},
            "release_commit_sha": {
                "type": "string",
                "pattern": "^[A-Fa-f0-9]{40}$",
            },
            "public_base_url": {
                "type": "string",
                "pattern": "^https://.+$",
            },
            "execute_api_endpoint": {
                "type": "string",
                "pattern": "^https://.+\\.execute-api\\..+$",
            },
            "cors_allowed_origins": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "stack_outputs": {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": False,
                "required": ["NovaPublicBaseUrl", "NovaRestApiEndpoint"],
                "properties": _STACK_OUTPUT_PROPERTIES,
            },
            "api_lambda_artifact": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "artifact_bucket",
                    "artifact_key",
                    "artifact_sha256",
                    "package_name",
                    "package_version",
                    "release_commit_sha",
                ],
                "properties": {
                    "artifact_bucket": {"type": "string", "minLength": 1},
                    "artifact_key": {"type": "string", "minLength": 1},
                    "artifact_sha256": {
                        "type": "string",
                        "pattern": "^[A-Fa-f0-9]{64}$",
                    },
                    "package_name": {"type": "string", "minLength": 1},
                    "package_version": {"type": "string", "minLength": 1},
                    "release_commit_sha": {
                        "type": "string",
                        "pattern": "^[A-Fa-f0-9]{40}$",
                    },
                },
            },
        },
    }


def build_workflow_deploy_runtime_schema() -> dict[str, Any]:
    """Return the reusable deploy-runtime workflow contract schema."""
    return {
        "$schema": _SCHEMA_URI,
        "$id": (
            "https://3m-cloud.github.io/nova/docs/contracts/"
            "workflow-deploy-runtime-v1.schema.json"
        ),
        "title": "Reusable Deploy Runtime workflow_call contract",
        "description": (
            "Contract for reusable deploy-runtime workflow inputs and outputs."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": ["inputs", "outputs"],
        "properties": {
            "inputs": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "release_apply_run_id",
                    "api_domain_name",
                    "certificate_arn",
                    "hosted_zone_id",
                    "hosted_zone_name",
                    "jwt_issuer",
                    "jwt_audience",
                    "jwt_jwks_url",
                    "runtime_cfn_execution_role_arn",
                ],
                "properties": {
                    "release_apply_run_id": {
                        "type": "string",
                        "pattern": "^[1-9][0-9]*$",
                    },
                    "release_apply_artifact_name": {
                        "type": "string",
                        "minLength": 1,
                        "default": "release-apply-artifacts",
                    },
                    "release_apply_repo": {
                        "type": "string",
                        "pattern": "^$|^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
                        "default": "",
                        "description": (
                            "Repository that owns the immutable release-apply "
                            "artifacts; when provided, it must match the "
                            "workflow source repository."
                        ),
                    },
                    "api_domain_name": {"type": "string", "minLength": 1},
                    "certificate_arn": {
                        "type": "string",
                        "pattern": "^arn:[^\\s]+:acm:[^\\s]+$",
                    },
                    "hosted_zone_id": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "hosted_zone_name": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "jwt_issuer": {
                        "type": "string",
                        "pattern": "^https://.+$",
                    },
                    "jwt_audience": {"type": "string", "minLength": 1},
                    "jwt_jwks_url": {
                        "type": "string",
                        "pattern": "^https://.+$",
                    },
                    "aws_region": {
                        "type": "string",
                        "pattern": "^[a-z]{2}-[a-z]+-\\d+$",
                        "default": "us-east-1",
                    },
                    "environment_name": {
                        "type": "string",
                        "minLength": 1,
                        "default": "dev",
                    },
                    "allowed_origins": {
                        "type": "string",
                        "default": "",
                    },
                    "deploy_output_artifact_name": {
                        "type": "string",
                        "minLength": 1,
                        "default": "deploy-runtime-output",
                    },
                    "runtime_cfn_execution_role_arn": {
                        "type": "string",
                        "pattern": "^arn:[^\\s]+:iam::\\d{12}:role/.+$",
                    },
                },
            },
            "outputs": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "deploy_output_artifact_name",
                    "deploy_output_path",
                    "deploy_output_sha256_path",
                    "deploy_output_sha256",
                    "public_base_url",
                    "runtime_version",
                    "release_commit_sha",
                    "stack_name",
                ],
                "properties": {
                    "deploy_output_artifact_name": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "deploy_output_path": {
                        "type": "string",
                        "pattern": "^[^\\s]+\\.json$",
                    },
                    "deploy_output_sha256_path": {
                        "type": "string",
                        "pattern": "^[^\\s]+\\.(sha256|txt)$",
                    },
                    "deploy_output_sha256": {
                        "type": "string",
                        "pattern": "^[A-Fa-f0-9]{64}$",
                    },
                    "public_base_url": {
                        "type": "string",
                        "pattern": "^https://.+$",
                    },
                    "runtime_version": {"type": "string", "minLength": 1},
                    "release_commit_sha": {
                        "type": "string",
                        "pattern": "^[A-Fa-f0-9]{40}$",
                    },
                    "stack_name": {"type": "string", "minLength": 1},
                },
            },
        },
    }


def _write_if_changed(path: Path, payload: dict[str, Any]) -> None:
    """Persist one schema file with stable formatting."""
    common.write_json(path, payload)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Write or check runtime deploy contract schemas."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if checked-in schemas differ from generated content.",
    )
    return parser.parse_args()


def _schema_text(payload: dict[str, Any]) -> str:
    """Return stable JSON text for a schema payload."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> int:
    """Generate or check runtime deploy schemas."""
    args = _parse_args()
    targets = {
        _DEPLOY_OUTPUT_PATH: build_deploy_output_schema(),
        _WORKFLOW_SCHEMA_PATH: build_workflow_deploy_runtime_schema(),
    }
    if args.check:
        mismatches = [
            str(path)
            for path, payload in targets.items()
            if not path.is_file()
            or path.read_text(encoding="utf-8") != _schema_text(payload)
        ]
        if mismatches:
            raise SystemExit(
                "Runtime deploy contract schemas are stale: "
                + ", ".join(sorted(mismatches))
            )
        return 0

    for path, payload in targets.items():
        _write_if_changed(path, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
