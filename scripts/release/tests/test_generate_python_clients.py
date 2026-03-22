"""Tests for public Python SDK generation helpers."""

from __future__ import annotations

from scripts.release.generate_python_clients import (
    _filter_internal_operations_for_public_sdk,
)


def test_filter_internal_operations_prunes_internal_only_paths() -> None:
    """Internal-only operations should be removed before generation."""
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/v1/public": {
                "get": {
                    "operationId": "get_public",
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/v1/internal": {
                "post": {
                    "operationId": "post_internal",
                    "x-nova-sdk-visibility": "internal",
                    "responses": {"202": {"description": "accepted"}},
                }
            },
            "/v1/mixed": {
                "get": {
                    "operationId": "get_mixed",
                    "responses": {"200": {"description": "ok"}},
                },
                "post": {
                    "operationId": "post_mixed_internal",
                    "x-nova-sdk-visibility": "internal",
                    "responses": {"202": {"description": "accepted"}},
                },
            },
        },
    }

    filtered = _filter_internal_operations_for_public_sdk(spec)

    assert "/v1/public" in filtered["paths"]
    assert filtered["paths"]["/v1/public"]["get"]["operationId"] == "get_public"
    assert "/v1/internal" not in filtered["paths"]
    assert "get" in filtered["paths"]["/v1/mixed"]
    assert "post" not in filtered["paths"]["/v1/mixed"]
