from __future__ import annotations

from nova_runtime_support import (
    SDK_VISIBILITY_EXTENSION,
    SDK_VISIBILITY_INTERNAL,
)

from scripts.release.generate_python_clients import (
    _filter_internal_operations_for_public_sdk,
)


def test_filter_internal_operations_removes_internal_only_paths() -> None:
    spec = {
        "paths": {
            "/v1/jobs": {
                "post": {"operationId": "create_job"},
            },
            "/v1/internal/jobs/{job_id}/result": {
                "post": {
                    "operationId": "update_job_result",
                    SDK_VISIBILITY_EXTENSION: SDK_VISIBILITY_INTERNAL,
                }
            },
        }
    }

    filtered = _filter_internal_operations_for_public_sdk(spec)

    assert "/v1/jobs" in filtered["paths"]
    assert "/v1/internal/jobs/{job_id}/result" not in filtered["paths"]


def test_filter_internal_operations_keeps_public_operations() -> None:
    spec = {
        "paths": {
            "/v1/token/verify": {
                "post": {"operationId": "verify_token"},
            },
            "/v1/token/introspect": {
                "post": {"operationId": "introspect_token"},
            },
        }
    }

    filtered = _filter_internal_operations_for_public_sdk(spec)

    assert filtered == spec
