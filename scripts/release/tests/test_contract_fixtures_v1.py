"""Contract fixture validation for canonical v1 fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nova_auth_api.models import (
    ErrorEnvelope as AuthErrorEnvelope,
)
from nova_auth_api.models import (
    TokenVerifyRequest,
    TokenVerifyResponse,
)
from nova_file_api.models import (
    EnqueueJobRequest,
    EnqueueJobResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    JobStatusResponse,
)
from nova_file_api.models import (
    ErrorEnvelope as FileErrorEnvelope,
)

FIXTURE_ROOT = Path("packages/contracts/fixtures/v1")


def _read_json(relative_path: str) -> dict[str, Any]:
    return json.loads(
        (FIXTURE_ROOT / relative_path).read_text(encoding="utf-8")
    )


def test_manifest_paths_exist() -> None:
    manifest = _read_json("manifest.json")

    for group in ("schemas", "fixtures"):
        assert group in manifest

    for schema_path in manifest["schemas"].values():
        assert (FIXTURE_ROOT / schema_path).is_file()

    for domain in manifest["fixtures"].values():
        for fixture_path in domain.values():
            assert (FIXTURE_ROOT / fixture_path).is_file()


def test_auth_verify_fixtures_match_contract_models() -> None:
    verify_request = {
        "access_token": "example-token",
        "required_scopes": ["jobs:enqueue"],
        "required_permissions": ["jobs:enqueue"],
    }
    TokenVerifyRequest.model_validate(verify_request)

    verify_success = _read_json("fixtures/auth/verify.success.json")
    TokenVerifyResponse.model_validate(verify_success)

    verify_401 = _read_json("fixtures/auth/verify.401.invalid-token.json")
    verify_403 = _read_json("fixtures/auth/verify.403.insufficient-scope.json")
    AuthErrorEnvelope.model_validate(verify_401)
    AuthErrorEnvelope.model_validate(verify_403)


def test_transfer_and_jobs_fixtures_match_contract_models() -> None:
    InitiateUploadRequest.model_validate(
        _read_json("fixtures/transfer/initiate.request.json")
    )
    InitiateUploadResponse.model_validate(
        _read_json("fixtures/transfer/initiate.success.json")
    )

    EnqueueJobRequest.model_validate(
        _read_json("fixtures/jobs/enqueue.request.json")
    )
    EnqueueJobResponse.model_validate(
        _read_json("fixtures/jobs/enqueue.success.json")
    )
    JobStatusResponse.model_validate(
        _read_json("fixtures/jobs/status.success.json")
    )

    queue_error = _read_json("fixtures/jobs/enqueue.503.queue-unavailable.json")
    FileErrorEnvelope.model_validate(queue_error)
