"""Deploy-output contract and provenance tests."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pytest import MonkeyPatch

from .helpers import load_repo_module, read_repo_file as _read

_GENERATOR = load_repo_module(
    "runtime_deploy_contract_generator",
    "scripts/release/generate_runtime_deploy_contract.py",
)
_RESOLVER = load_repo_module(
    "resolve_deploy_output",
    "scripts/release/resolve_deploy_output.py",
)
_VALIDATOR = load_repo_module(
    "validate_runtime_release",
    "scripts/release/validate_runtime_release.py",
)


def _canonical_sha256(payload: dict[str, object]) -> str:
    """Return the canonical SHA256 digest for a JSON object."""
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_schema(
    instance: Any,
    schema: dict[str, Any],
    *,
    defs: dict[str, Any],
    path: str = "$",
) -> None:
    """Validate a JSON instance against the checked-in report schema subset."""
    if "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/$defs/"), f"{path}: unsupported ref {ref!r}"
        _validate_schema(
            instance,
            defs[ref.removeprefix("#/$defs/")],
            defs=defs,
            path=path,
        )
        return

    for combinator in ("anyOf", "oneOf"):
        if combinator not in schema:
            continue
        branches = schema[combinator]
        errors: list[AssertionError] = []
        for branch in branches:
            try:
                _validate_schema(instance, branch, defs=defs, path=path)
            except AssertionError as exc:
                errors.append(exc)
            else:
                return
        raise AssertionError(
            f"{path}: no {combinator} branch matched; "
            f"last error: {errors[-1] if errors else 'none'}"
        )

    schema_type = schema.get("type")
    if schema_type == "object":
        assert isinstance(instance, dict), f"{path}: expected object"
        required = schema.get("required", [])
        for key in required:
            assert key in instance, f"{path}: missing required key {key!r}"
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(instance) - set(properties))
            assert not unexpected, f"{path}: unexpected keys {unexpected!r}"
        for key, value in instance.items():
            if key in properties:
                _validate_schema(
                    value,
                    properties[key],
                    defs=defs,
                    path=f"{path}.{key}",
                )
        return

    if schema_type == "array":
        assert isinstance(instance, list), f"{path}: expected array"
        min_items = schema.get("minItems")
        if min_items is not None:
            assert len(instance) >= min_items, (
                f"{path}: expected at least {min_items} items"
            )
        items = schema.get("items")
        if items is not None:
            for index, value in enumerate(instance):
                _validate_schema(
                    value,
                    items,
                    defs=defs,
                    path=f"{path}[{index}]",
                )
        return

    if schema_type == "string":
        assert isinstance(instance, str), f"{path}: expected string"
        min_length = schema.get("minLength")
        if min_length is not None:
            assert len(instance) >= min_length, (
                f"{path}: expected string length >= {min_length}"
            )
        pattern = schema.get("pattern")
        if pattern is not None:
            assert re.fullmatch(pattern, instance), (
                f"{path}: value {instance!r} does not match {pattern!r}"
            )
        if schema.get("format") == "date-time":
            datetime.fromisoformat(instance.replace("Z", "+00:00"))
        if "enum" in schema:
            assert instance in schema["enum"], (
                f"{path}: value {instance!r} is not in {schema['enum']!r}"
            )
        if "const" in schema:
            assert instance == schema["const"], (
                f"{path}: expected constant {schema['const']!r}"
            )
        return

    if schema_type == "integer":
        assert isinstance(instance, int) and not isinstance(instance, bool), (
            f"{path}: expected integer"
        )
        minimum = schema.get("minimum")
        if minimum is not None:
            assert instance >= minimum, f"{path}: expected >= {minimum}"
        return

    if schema_type == "boolean":
        assert isinstance(instance, bool), f"{path}: expected boolean"
        return

    if schema_type == "null":
        assert instance is None, f"{path}: expected null"
        return

    if schema_type is None:
        return

    raise AssertionError(f"{path}: unsupported schema type {schema_type!r}")


def test_runtime_deploy_contract_generator_is_in_sync() -> None:
    """Generated deploy-output schema must match the checked-in artifact."""
    assert (
        json.loads(
            _read("docs/contracts/deploy-output-authority-v2.schema.json")
        )
        == _GENERATOR.build_deploy_output_schema()
    )


def test_deploy_output_schema_covers_authoritative_fields() -> None:
    """Deploy-output schema must cover deploy provenance and stack outputs."""
    schema = json.loads(
        _read("docs/contracts/deploy-output-authority-v2.schema.json")
    )
    props = schema["properties"]
    stack_output_props = props["stack_outputs"]["properties"]

    for required in [
        "release_commit_sha",
        "runtime_version",
        "public_base_url",
        "execute_api_endpoint",
        "cors_allowed_origins",
        "stack_name",
        "region",
        "stack_outputs",
        "api_lambda_artifact",
    ]:
        assert required in props

    assert set(stack_output_props) == {
        "NovaAlarmTopicArn",
        "NovaApiAccessLogGroupName",
        "NovaExportWorkflowStateMachineArn",
        "NovaExportsTableName",
        "NovaIdempotencyTableName",
        "NovaPublicBaseUrl",
        "NovaRestApiEndpoint",
        "NovaWafLogGroupName",
    }
    assert props["stack_outputs"]["additionalProperties"] is False


def test_post_deploy_report_allows_localhost_cors_origin() -> None:
    """Validation reports must accept HTTPS production and localhost dev."""
    schema = json.loads(
        _read("docs/contracts/release-artifacts-v1.schema.json")
    )
    report_schema = schema["$defs"]["post_deploy_validation_report"]
    assert report_schema["properties"]["cors_origin"]["pattern"] == (
        "^(?:https://.+|http://localhost(?::\\d+)?)$"
    )


def test_resolve_deploy_output_builds_and_verifies_authority_payload(
    tmp_path: Path,
) -> None:
    """Resolver should normalize stack outputs into one authority payload."""
    api_lambda_artifact = {
        "artifact_bucket": "nova-artifacts",
        "artifact_key": (
            "runtime/nova-file-api/abc/def/nova-file-api-lambda.zip"
        ),
        "artifact_sha256": "1" * 64,
        "package_name": "nova-file-api",
        "package_version": "0.5.0",
        "release_commit_sha": "a" * 40,
        "runtime": "python3.13",
        "built_at": "2026-03-30T00:00:00+00:00",
    }
    workflow_lambda_artifact = {
        "artifact_bucket": "nova-artifacts",
        "artifact_key": (
            "runtime/nova-workflows/abc/def/nova-workflows-lambda.zip"
        ),
        "artifact_sha256": "3" * 64,
        "package_name": "nova-workflows",
        "package_version": "0.5.0",
        "release_commit_sha": "a" * 40,
        "runtime": "python3.13",
        "extra_field": "ignored",
    }
    payload = _RESOLVER.build_deploy_output(
        api_lambda_artifact=api_lambda_artifact,
        workflow_lambda_artifact=workflow_lambda_artifact,
        stack_name="NovaRuntimeStack",
        region="us-east-1",
        environment_name="prod",
        allowed_origins='["https://app.example.com"]',
        repository="3M-Cloud/nova",
        pipeline_name="nova-release-control-plane",
        pipeline_execution_id="execution-123",
        codebuild_build_ids=["build-dev-123", "build-prod-123"],
        stack_description={
            "Outputs": [
                {
                    "OutputKey": "ExportNovaPublicBaseUrl",
                    "ExportName": "NovaDevPublicBaseUrl",
                    "OutputValue": "https://api.example.com",
                },
                {
                    "OutputKey": "ExportNovaExportWorkflowStateMachineArn",
                    "ExportName": "NovaDevExportWorkflowStateMachineArn",
                    "OutputValue": (
                        "arn:aws:states:us-east-1:1:stateMachine:test"
                    ),
                },
                {
                    "OutputKey": "NovaRestApiEndpointADC846BC",
                    "OutputValue": (
                        "https://example.execute-api.us-east-1.amazonaws.com/dev/"
                    ),
                },
            ],
            "StackId": (
                "arn:aws:cloudformation:us-east-1:1:stack/NovaRuntimeStack/abc"
            ),
        },
    )

    assert payload["public_base_url"] == "https://api.example.com"
    assert (
        payload["execute_api_endpoint"]
        == "https://example.execute-api.us-east-1.amazonaws.com/dev"
    )
    assert payload["cors_allowed_origins"] == ["https://app.example.com"]
    assert payload["runtime_version"] == "0.5.0"
    assert (
        payload["stack_outputs"]["NovaPublicBaseUrl"]
        == "https://api.example.com"
    )
    assert payload["stack_outputs"]["NovaRestApiEndpoint"] == (
        "https://example.execute-api.us-east-1.amazonaws.com/dev"
    )
    expected_artifact_key = (
        "runtime/nova-file-api/abc/def/nova-file-api-lambda.zip"
    )
    assert payload["api_lambda_artifact"] == {
        "artifact_bucket": "nova-artifacts",
        "artifact_key": expected_artifact_key,
        "artifact_sha256": "1" * 64,
        "package_name": "nova-file-api",
        "package_version": "0.5.0",
        "release_commit_sha": "a" * 40,
    }
    assert payload["workflow_lambda_artifact"] == {
        "artifact_bucket": "nova-artifacts",
        "artifact_key": (
            "runtime/nova-workflows/abc/def/nova-workflows-lambda.zip"
        ),
        "artifact_sha256": "3" * 64,
        "package_name": "nova-workflows",
        "package_version": "0.5.0",
        "release_commit_sha": "a" * 40,
    }
    assert payload["execution"] == {
        "system": "aws-codepipeline",
        "pipeline_name": "nova-release-control-plane",
        "pipeline_execution_id": "execution-123",
        "codebuild_build_ids": ["build-dev-123", "build-prod-123"],
    }

    deploy_output_path = tmp_path / "deploy-output.json"
    deploy_output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sha256_path = tmp_path / "deploy-output.sha256"
    sha256_path.write_text(
        f"{_canonical_sha256(payload)}  {deploy_output_path.name}\n",
        encoding="utf-8",
    )

    resolved, digest = _RESOLVER.load_deploy_output(
        deploy_output_path=deploy_output_path,
        sha256_path=sha256_path,
    )

    assert resolved["release_commit_sha"] == "a" * 40
    assert digest == _canonical_sha256(payload)


def test_normalize_allowed_origins_rejects_malformed_json() -> None:
    """Malformed JSON input must fail with a clear validation error."""
    with pytest.raises(ValueError, match="allowed_origins JSON is malformed"):
        _RESOLVER._normalize_allowed_origins(
            raw_value='["https://app.example.com"',
            environment_name="prod",
        )


@pytest.mark.parametrize(
    ("pipeline_name", "pipeline_execution_id"),
    [
        ("", "execution-123"),
        ("nova-release-control-plane", ""),
        ("   ", "execution-123"),
        ("nova-release-control-plane", "   "),
    ],
)
def test_build_deploy_output_rejects_blank_pipeline_identifiers(
    pipeline_name: str,
    pipeline_execution_id: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "pipeline_name and pipeline_execution_id must be non-empty strings"
        ),
    ):
        _RESOLVER.build_deploy_output(
            api_lambda_artifact={
                "artifact_bucket": "nova-artifacts",
                "artifact_key": (
                    "runtime/nova-file-api/abc/def/nova-file-api-lambda.zip"
                ),
                "artifact_sha256": "1" * 64,
                "package_name": "nova-file-api",
                "package_version": "0.5.0",
                "release_commit_sha": "a" * 40,
            },
            workflow_lambda_artifact={
                "artifact_bucket": "nova-artifacts",
                "artifact_key": (
                    "runtime/nova-workflows/abc/def/nova-workflows-lambda.zip"
                ),
                "artifact_sha256": "3" * 64,
                "package_name": "nova-workflows",
                "package_version": "0.5.0",
                "release_commit_sha": "a" * 40,
            },
            stack_name="NovaRuntimeStack",
            region="us-east-1",
            environment_name="prod",
            allowed_origins='["https://app.example.com"]',
            repository="3M-Cloud/nova",
            pipeline_name=pipeline_name,
            pipeline_execution_id=pipeline_execution_id,
            codebuild_build_ids=["build-dev-123"],
            stack_description={
                "Outputs": [
                    {
                        "OutputKey": "ExportNovaPublicBaseUrl",
                        "OutputName": "NovaDevPublicBaseUrl",
                        "OutputValue": "https://api.example.com",
                    },
                    {
                        "OutputKey": "ExportNovaExportWorkflowStateMachineArn",
                        "OutputName": "NovaDevExportWorkflowStateMachineArn",
                        "OutputValue": (
                            "arn:aws:states:us-east-1:1:stateMachine:test"
                        ),
                    },
                    {
                        "OutputKey": "NovaRestApiEndpointADC846BC",
                        "OutputValue": (
                            "https://example.execute-api.us-east-1.amazonaws.com/dev/"
                        ),
                    },
                ],
            },
        )


@pytest.mark.parametrize(
    ("raw_value", "exc_type", "match"),
    [
        (
            "app.example.com",
            ValueError,
            "invalid allowed_origin: app.example.com",
        ),
        ("[1]", TypeError, "invalid allowed_origin: 1"),
        (
            "https://app.example.com/path",
            ValueError,
            "invalid allowed_origin: https://app.example.com/path",
        ),
    ],
)
def test_normalize_allowed_origins_rejects_invalid_origins(
    raw_value: str,
    exc_type: type[Exception],
    match: str,
) -> None:
    """Bare hostnames and non-origin values must fail normalization."""
    with pytest.raises(exc_type, match=match):
        _RESOLVER._normalize_allowed_origins(
            raw_value=raw_value,
            environment_name="dev",
        )


def test_validate_runtime_release_binds_report_to_deploy_output(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Validation report must retain deploy-output provenance and auth truth."""
    payload = {
        "schema_version": "2.0",
        "captured_at": "2026-03-29T00:00:00+00:00",
        "repository": "3M-Cloud/nova",
        "execution": {
            "system": "aws-codepipeline",
            "pipeline_name": "nova-release-control-plane",
            "pipeline_execution_id": "execution-123",
            "codebuild_build_ids": ["build-dev-123", "build-prod-123"],
        },
        "stack_name": "NovaRuntimeStack",
        "region": "us-east-1",
        "environment": "prod",
        "runtime_name": "nova-file-api",
        "runtime_version": "0.5.0",
        "release_commit_sha": "b" * 40,
        "public_base_url": "https://api.example.com",
        "execute_api_endpoint": (
            "https://example.execute-api.us-east-1.amazonaws.com/dev"
        ),
        "cors_allowed_origins": ["https://app.example.com"],
        "stack_outputs": {
            "NovaPublicBaseUrl": "https://api.example.com",
            "NovaRestApiEndpoint": (
                "https://example.execute-api.us-east-1.amazonaws.com/dev"
            ),
            "NovaApiAccessLogGroupName": (
                "/aws/apigateway/nova-rest-api-access-dev"
            ),
        },
        "api_lambda_artifact": {
            "artifact_bucket": "nova-artifacts",
            "artifact_key": (
                "runtime/nova-file-api/abc/def/nova-file-api-lambda.zip"
            ),
            "artifact_sha256": "2" * 64,
            "package_name": "nova-file-api",
            "package_version": "0.5.0",
            "release_commit_sha": "b" * 40,
        },
        "workflow_lambda_artifact": {
            "artifact_bucket": "nova-artifacts",
            "artifact_key": (
                "runtime/nova-workflows/abc/def/nova-workflows-lambda.zip"
            ),
            "artifact_sha256": "3" * 64,
            "package_name": "nova-workflows",
            "package_version": "0.5.0",
            "release_commit_sha": "b" * 40,
        },
    }
    deploy_output_path = tmp_path / "deploy-output.json"
    deploy_output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = _canonical_sha256(payload)
    sha256_path = tmp_path / "deploy-output.sha256"
    sha256_path.write_text(
        f"{digest}  {deploy_output_path.name}\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "validation-report.json"

    def fake_request(
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> Any:
        del body
        if url.startswith("https://example.execute-api.") and url.endswith(
            "/v1/releases/info"
        ):
            return _VALIDATOR.RequestResult(
                status_code=403,
                headers={},
                body=b'{"message":"Forbidden"}',
                error=None,
            )
        if url.endswith("/v1/releases/info"):
            return _VALIDATOR.RequestResult(
                status_code=200,
                headers={},
                body=json.dumps(
                    {
                        "name": "nova-file-api",
                        "version": "0.5.0",
                        "environment": "prod",
                    }
                ).encode("utf-8"),
                error=None,
            )
        if method == "OPTIONS" and url.endswith("/v1/exports"):
            return _VALIDATOR.RequestResult(
                status_code=200,
                headers={
                    "access-control-allow-origin": (headers or {}).get(
                        "Origin", ""
                    ),
                    "access-control-allow-methods": "GET, POST, OPTIONS",
                    "access-control-allow-headers": (
                        "Authorization, Content-Type, Idempotency-Key, "
                        "X-Request-Id"
                    ),
                },
                body=b"OK",
                error=None,
            )
        if url.endswith("/v1/exports"):
            return _VALIDATOR.RequestResult(
                status_code=401,
                headers={
                    "access-control-allow-origin": (headers or {}).get(
                        "Origin", ""
                    )
                },
                body=b"{}",
                error=None,
            )
        if url.endswith("/healthz") or url.endswith("/readyz"):
            return _VALIDATOR.RequestResult(
                status_code=404,
                headers={},
                body=b"{}",
                error=None,
            )
        return _VALIDATOR.RequestResult(
            status_code=200,
            headers={},
            body=b"{}",
            error=None,
        )

    monkeypatch.setattr(_VALIDATOR, "_request", fake_request)
    monkeypatch.setattr(
        _VALIDATOR,
        "_validate_reserved_concurrency",
        lambda *, deploy_output, failures: [
            _VALIDATOR.ConcurrencyCheck(
                function_group="api",
                function_logical_id="NovaApiFunctionF531316A",
                function_name="nova-api",
                expected_reserved_concurrency=25,
                actual_reserved_concurrency=25,
                ok=True,
            ),
            _VALIDATOR.ConcurrencyCheck(
                function_group="workflow",
                function_logical_id="ValidateExportFunctionE0F66E1E",
                function_name="validate-export",
                expected_reserved_concurrency=10,
                actual_reserved_concurrency=10,
                ok=True,
            ),
        ],
    )
    monkeypatch.setattr(
        _VALIDATOR,
        "_args",
        lambda: Namespace(
            deploy_output_path=str(deploy_output_path),
            deploy_output_sha256_path=str(sha256_path),
            canonical_paths=(
                "/v1/health/live,/v1/health/ready,"
                "/v1/capabilities,/v1/releases/info"
            ),
            protected_paths="POST /v1/exports",
            legacy_404_paths="/healthz,/readyz",
            cors_preflight_path="/v1/exports",
            cors_origin="",
            report_path=str(report_path),
        ),
    )

    assert _VALIDATOR.main() == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["deploy_output_sha256"] == digest
    assert report["release_commit_sha"] == "b" * 40
    assert report["runtime_version"] == "0.5.0"
    assert report["release_info"]["version"] == "0.5.0"
    assert report["execute_api_endpoint"] == (
        "https://example.execute-api.us-east-1.amazonaws.com/dev"
    )
    assert report["protected_paths"] == ["POST /v1/exports"]
    assert report["cors_preflight_path"] == "/v1/exports"
    assert report["cors_allowed_origins"] == ["https://app.example.com"]
    assert report["cors_origin"] == "https://app.example.com"
    assert report["concurrency_checks"] == [
        {
            "function_group": "api",
            "function_logical_id": "NovaApiFunctionF531316A",
            "function_name": "nova-api",
            "expected_reserved_concurrency": 25,
            "actual_reserved_concurrency": 25,
            "ok": True,
        },
        {
            "function_group": "workflow",
            "function_logical_id": "ValidateExportFunctionE0F66E1E",
            "function_name": "validate-export",
            "expected_reserved_concurrency": 10,
            "actual_reserved_concurrency": 10,
            "ok": True,
        },
    ]
    assert {check["kind"] for check in report["checks"]} == {
        "canonical",
        "protected",
        "legacy_404",
        "cors_preflight",
        "execute_api_disabled",
    }


def test_validate_runtime_release_keeps_failed_report_schema_valid(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Failed validation still needs to emit a schema-valid report."""
    payload = {
        "schema_version": "2.0",
        "captured_at": "2026-03-29T00:00:00+00:00",
        "repository": "3M-Cloud/nova",
        "execution": {
            "system": "aws-codepipeline",
            "pipeline_name": "nova-release-control-plane",
            "pipeline_execution_id": "execution-123",
            "codebuild_build_ids": ["build-dev-123"],
        },
        "stack_name": "NovaRuntimeStack",
        "region": "us-east-1",
        "environment": "prod",
        "runtime_name": "nova-file-api",
        "runtime_version": "0.5.0",
        "release_commit_sha": "b" * 40,
        "public_base_url": "https://api.example.com",
        "execute_api_endpoint": (
            "https://example.execute-api.us-east-1.amazonaws.com/dev"
        ),
        "cors_allowed_origins": ["https://app.example.com"],
        "stack_outputs": {
            "NovaPublicBaseUrl": "https://api.example.com",
            "NovaRestApiEndpoint": (
                "https://example.execute-api.us-east-1.amazonaws.com/dev"
            ),
            "NovaApiAccessLogGroupName": (
                "/aws/apigateway/nova-rest-api-access-dev"
            ),
        },
        "api_lambda_artifact": {
            "artifact_bucket": "nova-artifacts",
            "artifact_key": (
                "runtime/nova-file-api/abc/def/nova-file-api-lambda.zip"
            ),
            "artifact_sha256": "2" * 64,
            "package_name": "nova-file-api",
            "package_version": "0.5.0",
            "release_commit_sha": "b" * 40,
        },
        "workflow_lambda_artifact": {
            "artifact_bucket": "nova-artifacts",
            "artifact_key": (
                "runtime/nova-workflows/abc/def/nova-workflows-lambda.zip"
            ),
            "artifact_sha256": "3" * 64,
            "package_name": "nova-workflows",
            "package_version": "0.5.0",
            "release_commit_sha": "b" * 40,
        },
    }
    deploy_output_path = tmp_path / "deploy-output.json"
    deploy_output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = _canonical_sha256(payload)
    sha256_path = tmp_path / "deploy-output.sha256"
    sha256_path.write_text(
        f"{digest}  {deploy_output_path.name}\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "validation-report.json"

    def fake_request(
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> Any:
        del body
        if url.startswith("https://example.execute-api.") and url.endswith(
            "/v1/releases/info"
        ):
            return _VALIDATOR.RequestResult(
                status_code=403,
                headers={},
                body=b"{}",
                error=None,
            )
        if url.endswith("/v1/releases/info"):
            return _VALIDATOR.RequestResult(
                status_code=500,
                headers={},
                body=b"{}",
                error=None,
            )
        if method == "OPTIONS" and url.endswith("/v1/exports"):
            return _VALIDATOR.RequestResult(
                status_code=200,
                headers={
                    "access-control-allow-origin": (headers or {}).get(
                        "Origin", ""
                    ),
                    "access-control-allow-methods": "GET, POST, OPTIONS",
                    "access-control-allow-headers": (
                        "Authorization, Content-Type, Idempotency-Key, "
                        "X-Request-Id"
                    ),
                },
                body=b"OK",
                error=None,
            )
        if url.endswith("/v1/exports"):
            return _VALIDATOR.RequestResult(
                status_code=401,
                headers={
                    "access-control-allow-origin": (headers or {}).get(
                        "Origin", ""
                    )
                },
                body=b"{}",
                error=None,
            )
        if url.endswith("/healthz") or url.endswith("/readyz"):
            return _VALIDATOR.RequestResult(
                status_code=404,
                headers={},
                body=b"{}",
                error=None,
            )
        return _VALIDATOR.RequestResult(
            status_code=200,
            headers={},
            body=b"{}",
            error=None,
        )

    monkeypatch.setattr(_VALIDATOR, "_request", fake_request)
    monkeypatch.setattr(
        _VALIDATOR,
        "_validate_reserved_concurrency",
        lambda *, deploy_output, failures: [
            _VALIDATOR.ConcurrencyCheck(
                function_group="api",
                function_logical_id="NovaApiFunctionF531316A",
                function_name="nova-api",
                expected_reserved_concurrency=25,
                actual_reserved_concurrency=None,
                ok=False,
            )
        ],
    )
    monkeypatch.setattr(
        _VALIDATOR,
        "_args",
        lambda: Namespace(
            deploy_output_path=str(deploy_output_path),
            deploy_output_sha256_path=str(sha256_path),
            canonical_paths=(
                "/v1/health/live,/v1/health/ready,"
                "/v1/capabilities,/v1/releases/info"
            ),
            protected_paths="POST /v1/exports",
            legacy_404_paths="/healthz,/readyz",
            cors_preflight_path="/v1/exports",
            cors_origin="",
            report_path=str(report_path),
        ),
    )

    with pytest.raises(SystemExit, match="Validation failed:"):
        _VALIDATOR.main()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    _validate_schema(
        report,
        _VALIDATOR.load_report_schema(),
        defs=_VALIDATOR.REPORT_SCHEMA["$defs"],
    )
    assert report["status"] == "failed"
    assert report["release_info"] is None
    assert report["deploy_output_sha256"] == digest
    assert report["concurrency_checks"] == [
        {
            "function_group": "api",
            "function_logical_id": "NovaApiFunctionF531316A",
            "function_name": "nova-api",
            "expected_reserved_concurrency": 25,
            "actual_reserved_concurrency": None,
            "ok": False,
        }
    ]


def test_aws_cli_json_forces_json_output_and_timeout(
    monkeypatch: MonkeyPatch,
) -> None:
    """AWS CLI wrapper should force JSON output and a bounded timeout."""

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> Any:
        assert command[:5] == [
            "aws",
            "--no-cli-pager",
            "--output",
            "json",
            "lambda",
        ]
        assert check is False
        assert capture_output is True
        assert text is True
        assert timeout == _VALIDATOR._AWS_CLI_TIMEOUT_SECONDS

        class Result:
            returncode = 0
            stdout = '{"ReservedConcurrentExecutions": 0}'
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert _VALIDATOR._aws_cli_json(
        "lambda",
        "get-function-concurrency",
        "--function-name",
        "nova-api",
    ) == {"ReservedConcurrentExecutions": 0}


def test_validate_runtime_release_emits_report_when_concurrency_lookup_raises(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Concurrency lookup errors should not suppress the report artifact."""
    payload = {
        "schema_version": "2.0",
        "captured_at": "2026-03-29T00:00:00+00:00",
        "repository": "BjornMelin/nova",
        "execution": {
            "system": "aws-codepipeline",
            "pipeline_name": "nova-release-control-plane",
            "pipeline_execution_id": "execution-123",
            "codebuild_build_ids": ["build-dev-123"],
        },
        "stack_name": "NovaRuntimeStack",
        "region": "us-east-1",
        "environment": "prod",
        "runtime_name": "nova-file-api",
        "runtime_version": "0.5.0",
        "release_commit_sha": "b" * 40,
        "public_base_url": "https://api.example.com",
        "execute_api_endpoint": (
            "https://example.execute-api.us-east-1.amazonaws.com/dev"
        ),
        "cors_allowed_origins": ["https://app.example.com"],
        "stack_outputs": {
            "NovaPublicBaseUrl": "https://api.example.com",
            "NovaRestApiEndpoint": (
                "https://example.execute-api.us-east-1.amazonaws.com/dev"
            ),
        },
        "api_lambda_artifact": {
            "artifact_bucket": "nova-artifacts",
            "artifact_key": (
                "runtime/nova-file-api/abc/def/nova-file-api-lambda.zip"
            ),
            "artifact_sha256": "2" * 64,
            "package_name": "nova-file-api",
            "package_version": "0.5.0",
            "release_commit_sha": "b" * 40,
        },
        "workflow_lambda_artifact": {
            "artifact_bucket": "nova-artifacts",
            "artifact_key": (
                "runtime/nova-workflows/abc/def/nova-workflows-lambda.zip"
            ),
            "artifact_sha256": "3" * 64,
            "package_name": "nova-workflows",
            "package_version": "0.5.0",
            "release_commit_sha": "b" * 40,
        },
    }
    deploy_output_path = tmp_path / "deploy-output.json"
    deploy_output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sha256_path = tmp_path / "deploy-output.sha256"
    sha256_path.write_text(
        f"{_canonical_sha256(payload)}  {deploy_output_path.name}\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "validation-report.json"

    def fake_request(
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> Any:
        del body
        if url.startswith("https://example.execute-api.") and url.endswith(
            "/v1/releases/info"
        ):
            return _VALIDATOR.RequestResult(
                status_code=403,
                headers={},
                body=b"{}",
                error=None,
            )
        if url.endswith("/v1/releases/info"):
            return _VALIDATOR.RequestResult(
                status_code=200,
                headers={},
                body=json.dumps(
                    {
                        "name": "nova-file-api",
                        "version": "0.5.0",
                        "environment": "prod",
                    }
                ).encode("utf-8"),
                error=None,
            )
        if method == "OPTIONS" and url.endswith("/v1/exports"):
            return _VALIDATOR.RequestResult(
                status_code=200,
                headers={
                    "access-control-allow-origin": (headers or {}).get(
                        "Origin", ""
                    ),
                    "access-control-allow-methods": "GET, POST, OPTIONS",
                    "access-control-allow-headers": (
                        "Authorization, Content-Type, Idempotency-Key"
                    ),
                },
                body=b"OK",
                error=None,
            )
        if url.endswith("/v1/exports"):
            return _VALIDATOR.RequestResult(
                status_code=401,
                headers={
                    "access-control-allow-origin": (headers or {}).get(
                        "Origin", ""
                    )
                },
                body=b"{}",
                error=None,
            )
        if url.endswith("/healthz") or url.endswith("/readyz"):
            return _VALIDATOR.RequestResult(
                status_code=404,
                headers={},
                body=b"{}",
                error=None,
            )
        return _VALIDATOR.RequestResult(
            status_code=200,
            headers={},
            body=b"{}",
            error=None,
        )

    monkeypatch.setattr(_VALIDATOR, "_request", fake_request)

    def raise_concurrency_error(
        *,
        deploy_output: dict[str, Any],
        failures: list[str],
    ) -> list[_VALIDATOR.ConcurrencyCheck]:
        del deploy_output, failures
        raise RuntimeError("boom")

    monkeypatch.setattr(
        _VALIDATOR,
        "_validate_reserved_concurrency",
        raise_concurrency_error,
    )
    monkeypatch.setattr(
        _VALIDATOR,
        "_args",
        lambda: Namespace(
            deploy_output_path=str(deploy_output_path),
            deploy_output_sha256_path=str(sha256_path),
            canonical_paths=(
                "/v1/health/live,/v1/health/ready,"
                "/v1/capabilities,/v1/releases/info"
            ),
            protected_paths="POST /v1/exports",
            legacy_404_paths="/healthz,/readyz",
            cors_preflight_path="/v1/exports",
            cors_origin="",
            report_path=str(report_path),
        ),
    )

    with pytest.raises(SystemExit, match="Validation failed:"):
        _VALIDATOR.main()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    _validate_schema(
        report,
        _VALIDATOR.load_report_schema(),
        defs=_VALIDATOR.REPORT_SCHEMA["$defs"],
    )
    assert report["concurrency_checks"] == []
    assert any(
        "reserved concurrency validation failed" in failure
        for failure in report["failures"]
    )
