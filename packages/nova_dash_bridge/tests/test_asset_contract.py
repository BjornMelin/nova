from __future__ import annotations

from pathlib import Path


def _file_transfer_asset_source() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    asset_path = (
        repo_root
        / "packages"
        / "nova_dash_bridge"
        / "src"
        / "nova_dash_bridge"
        / "assets"
        / "file_transfer.js"
    )
    return asset_path.read_text(encoding="utf-8")


def test_asset_keeps_bearer_only_auth_contract() -> None:
    source = _file_transfer_asset_source()

    assert "function getAuthorizationHeader(config)" in source
    assert 'root.dataset.authHeaderElementId || ""' in source
    assert "authorizedHeaders(config)" in source
    assert "config.authHeader = getAuthorizationHeader(config);" not in source
    assert "merged.Authorization = authorizationHeader" in source
    assert "X-Session-Id" not in source
    assert "session_id" not in source
    assert 'credentials: "same-origin"' not in source
    # `source` is file_transfer.js: three fetch helpers (postJson, getJson,
    # putWithTimeout) each embed exactly one credentials: "omit" so API JSON
    # and presigned PUTs stay bearer-only (no cookie/session creds). The
    # count guardrails that invariant if a helper is duplicated
    # or one drops omit.
    assert source.count('credentials: "omit"') >= 3


def test_asset_keeps_resume_and_canonical_endpoint_contracts() -> None:
    source = _file_transfer_asset_source()

    assert "function multipartStateStorageKey(config, file)" in source
    assert "storage.setItem(storageKey, JSON.stringify(state));" in source
    assert "storage.removeItem(storageKey);" in source
    assert "window.localStorage" in source
    assert 'base + "/uploads/introspect"' in source
    assert 'config.transfersEndpointBase + "/downloads/presign"' in source
    assert 'config.transfersEndpointBase + "/uploads/initiate"' in source
    assert "multipart upload completion is ambiguous" in source


def test_asset_keeps_progressive_sign_batch_controls() -> None:
    source = _file_transfer_asset_source()

    assert 'root.dataset.signBatchSize || ""' in source
    assert "configuredBatchSize > 0" in source
    assert "configuredBatchSize" in source
    assert "Math.min(16, Math.max(1, maxConcurrency * 2))" in source
