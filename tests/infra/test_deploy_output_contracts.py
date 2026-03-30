"""Deploy-output contract and provenance tests."""

from __future__ import annotations

import hashlib
import json
from argparse import Namespace
from pathlib import Path

from pytest import MonkeyPatch

from .helpers import load_repo_module
from .helpers import read_repo_file as _read

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


def test_runtime_deploy_contract_generator_is_in_sync() -> None:
    """Generated runtime deploy schemas must match checked-in artifacts."""
    assert (
        json.loads(
            _read("docs/contracts/deploy-output-authority-v2.schema.json")
        )
        == _GENERATOR.build_deploy_output_schema()
    )
    assert (
        json.loads(
            _read("docs/contracts/workflow-deploy-runtime-v1.schema.json")
        )
        == _GENERATOR.build_workflow_deploy_runtime_schema()
    )


def test_deploy_output_schema_covers_authoritative_fields() -> None:
    """Deploy-output schema must cover deploy provenance and stack outputs."""
    schema = json.loads(
        _read("docs/contracts/deploy-output-authority-v2.schema.json")
    )
    props = schema["properties"]

    for required in [
        "release_commit_sha",
        "runtime_version",
        "public_base_url",
        "stack_name",
        "region",
        "stack_outputs",
        "api_lambda_artifact",
    ]:
        assert required in props


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
    payload = _RESOLVER.build_deploy_output(
        api_lambda_artifact=api_lambda_artifact,
        stack_name="NovaRuntimeStack",
        region="us-east-1",
        environment_name="prod",
        repository="3M-Cloud/nova",
        deploy_run_id=123,
        deploy_run_attempt=1,
        deploy_workflow_ref=(
            "3M-Cloud/nova/.github/workflows/deploy-runtime.yml@refs/heads/main"
        ),
        stack_description={
            "Outputs": [
                {
                    "OutputKey": "NovaPublicBaseUrl",
                    "ExportName": "NovaPublicBaseUrl",
                    "OutputValue": "https://api.example.com",
                },
                {
                    "OutputKey": "NovaExportWorkflowStateMachineArn",
                    "ExportName": "NovaExportWorkflowStateMachineArn",
                    "OutputValue": (
                        "arn:aws:states:us-east-1:1:stateMachine:test"
                    ),
                },
            ],
            "StackId": (
                "arn:aws:cloudformation:us-east-1:1:stack/NovaRuntimeStack/abc"
            ),
        },
    )

    assert payload["public_base_url"] == "https://api.example.com"
    assert payload["runtime_version"] == "0.5.0"
    assert (
        payload["stack_outputs"]["NovaPublicBaseUrl"]
        == "https://api.example.com"
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


def test_validate_runtime_release_binds_report_to_deploy_output(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Validation report must retain deploy-output provenance."""
    payload = {
        "schema_version": "2.0",
        "captured_at": "2026-03-29T00:00:00+00:00",
        "repository": "3M-Cloud/nova",
        "deploy_run_id": 123,
        "deploy_run_attempt": 1,
        "deploy_workflow_ref": (
            "3M-Cloud/nova/.github/workflows/deploy-runtime.yml@refs/heads/main"
        ),
        "stack_name": "NovaRuntimeStack",
        "region": "us-east-1",
        "environment": "prod",
        "runtime_name": "nova-file-api",
        "runtime_version": "0.5.0",
        "release_commit_sha": "b" * 40,
        "public_base_url": "https://api.example.com",
        "stack_outputs": {
            "NovaPublicBaseUrl": "https://api.example.com",
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

    def fake_fetch(url: str) -> tuple[int | None, bytes | None, str | None]:
        if url.endswith("/v1/releases/info"):
            body = json.dumps(
                {
                    "name": "nova-file-api",
                    "version": "0.5.0",
                    "environment": "prod",
                }
            ).encode("utf-8")
            return 200, body, None
        if url.endswith("/healthz") or url.endswith("/readyz"):
            return 404, b"{}", None
        return 200, b"{}", None

    monkeypatch.setattr(_VALIDATOR, "_fetch", fake_fetch)
    monkeypatch.setattr(
        _VALIDATOR,
        "_args",
        lambda: Namespace(
            deploy_output_path=str(deploy_output_path),
            deploy_output_sha256_path=str(sha256_path),
            canonical_paths=(
                "/v1/health/live,/v1/health/ready,/metrics/summary,"
                "/v1/capabilities,/v1/releases/info"
            ),
            legacy_404_paths="/healthz,/readyz",
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
