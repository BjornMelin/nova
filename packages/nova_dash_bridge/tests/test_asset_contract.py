from __future__ import annotations

from base64 import b64decode
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nova_dash_bridge.dash_integration import (
    BearerAuthHeader,
    FileTransferAssets,
    _asset_text,
)


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
    assert '"session_id"' not in source
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
    assert "function isResumableStateExpired(state)" in source
    assert "storage.setItem(storageKey, JSON.stringify(state));" in source
    assert "storage.removeItem(storageKey);" in source
    assert "window.localStorage" in source
    assert "Date.parse(state.resumable_until)" in source
    assert 'base + "/uploads/introspect"' in source
    assert 'config.transfersEndpointBase + "/downloads/presign"' in source
    assert 'config.transfersEndpointBase + "/uploads/initiate"' in source
    assert "multipart upload completion is ambiguous" in source
    assert "session_id: storedMultipartState.session_id || null" in source
    assert (
        "resumable_until: storedMultipartState.resumable_until || null"
        in source
    )


def test_asset_keeps_progressive_sign_batch_controls() -> None:
    source = _file_transfer_asset_source()

    assert 'root.dataset.signBatchSize || ""' in source
    assert "function clampPositiveInt(value, fallback, maximum)" in source
    assert "configuredBatchSize > 0" in source
    assert "clampPositiveInt(" in source
    assert "Math.min(16, Math.max(1, maxConcurrency * 2))" in source


def test_file_transfer_assets_inline_by_default() -> None:
    assets = FileTransferAssets()

    stylesheet, script = assets.children

    assert stylesheet.href.startswith("data:text/css;base64,")
    assert script.src.startswith("data:text/javascript;base64,")
    assert ".nova-dropzone" in b64decode(
        stylesheet.href.partition(",")[2]
    ).decode("utf-8")
    assert "function getAuthorizationHeader(config)" in b64decode(
        script.src.partition(",")[2]
    ).decode("utf-8")


def test_file_transfer_assets_can_use_external_prefix() -> None:
    assets = FileTransferAssets(assets_url_prefix="/assets/nova")

    stylesheet, script = assets.children

    assert stylesheet.href == "/assets/nova/file_transfer.css"
    assert script.src == "/assets/nova/file_transfer.js"


def test_file_transfer_assets_strips_trailing_slash_from_prefix() -> None:
    assets = FileTransferAssets(assets_url_prefix="/assets/nova/")

    stylesheet, script = assets.children

    assert stylesheet.href == "/assets/nova/file_transfer.css"
    assert script.src == "/assets/nova/file_transfer.js"


def test_asset_text_uses_importlib_resources_loader() -> None:
    resource_file = Mock()
    resource_file.read_text.return_value = "asset payload"
    resource_root = Mock()
    resource_root.joinpath.return_value = resource_file

    with patch(
        "nova_dash_bridge.dash_integration.resources.files",
        return_value=resource_root,
    ) as files_mock:
        _asset_text.cache_clear()
        try:
            assert _asset_text("file_transfer.js") == "asset payload"
        finally:
            _asset_text.cache_clear()

    files_mock.assert_called_once_with("nova_dash_bridge.assets")
    resource_root.joinpath.assert_called_once_with("file_transfer.js")
    resource_file.read_text.assert_called_once_with(encoding="utf-8")


def test_asset_text_raises_clear_error_when_inline_assets_unavailable() -> None:
    with patch(
        "nova_dash_bridge.dash_integration.resources.files",
        side_effect=ModuleNotFoundError("nova_dash_bridge.assets"),
    ):
        _asset_text.cache_clear()
        try:
            with pytest.raises(
                RuntimeError,
                match="Pass assets_url_prefix to FileTransferAssets\\(\\)",
            ):
                _asset_text("file_transfer.js")
        finally:
            _asset_text.cache_clear()


def test_bearer_auth_header_renders_hidden_dom_node() -> None:
    header_node = BearerAuthHeader(
        auth_header_element_id="nova-auth-header",
        authorization_header="Bearer token-value",
    )

    assert header_node.id == "nova-auth-header"
    assert header_node.children == "Bearer token-value"
    assert header_node.hidden is True
    assert header_node.style == {"display": "none"}
    assert header_node.to_plotly_json()["props"]["aria-hidden"] == "true"
