#!/usr/bin/env python3
"""Generate the deploy-output authority schema."""

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
    "NovaExportCopyPartsTableName": {"type": "string", "minLength": 1},
    "NovaExportsTableName": {"type": "string", "minLength": 1},
    "NovaIdempotencyTableName": {"type": "string", "minLength": 1},
    "NovaObservabilityDashboardName": {"type": "string", "minLength": 1},
    "NovaPublicBaseUrl": {
        "type": "string",
        "pattern": "^https://.+$",
    },
    "NovaRestApiEndpoint": {
        "type": "string",
        "pattern": "^https://.+\\.execute-api\\..+$",
    },
    "NovaStorageLensConfigurationId": {"type": "string", "minLength": 1},
    "NovaTransferPolicyAppConfigApplicationId": {
        "type": "string",
        "minLength": 1,
    },
    "NovaTransferPolicyAppConfigEnvironmentId": {
        "type": "string",
        "minLength": 1,
    },
    "NovaTransferPolicyAppConfigProfileId": {
        "type": "string",
        "minLength": 1,
    },
    "NovaTransferSpendBudgetName": {"type": "string", "minLength": 1},
    "NovaTransferUsageTableName": {"type": "string", "minLength": 1},
    "NovaUploadSessionsTableName": {"type": "string", "minLength": 1},
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
            "AWS-native release control plane."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": [
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
        ],
        "properties": {
            "schema_version": {"type": "string", "const": "2.0"},
            "captured_at": {"type": "string", "format": "date-time"},
            "repository": {
                "type": "string",
                "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
            },
            "execution": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "system",
                    "pipeline_name",
                    "pipeline_execution_id",
                ],
                "properties": {
                    "system": {
                        "type": "string",
                        "const": "aws-codepipeline",
                    },
                    "pipeline_name": {"type": "string", "minLength": 1},
                    "pipeline_execution_id": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "codebuild_build_ids": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                },
            },
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
            "workflow_lambda_artifact": {
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write or check the deploy-output authority schema."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the checked-in schema differs from generated content.",
    )
    return parser.parse_args()


def _schema_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> int:
    """Write or check the deploy-output authority schema."""
    args = _parse_args()
    payload = build_deploy_output_schema()
    if args.check:
        if not _DEPLOY_OUTPUT_PATH.is_file() or _DEPLOY_OUTPUT_PATH.read_text(
            encoding="utf-8"
        ) != _schema_text(payload):
            raise SystemExit(
                "Runtime deploy contract schema is stale: "
                f"{_DEPLOY_OUTPUT_PATH}"
            )
        return 0

    common.write_json(_DEPLOY_OUTPUT_PATH, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
