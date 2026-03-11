from __future__ import annotations

import re
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


def test_poll_async_job_forwards_session_scope_header() -> None:
    source = _file_transfer_asset_source()

    assert "async function pollAsyncJob(config, jobId, sessionId)" in source
    assert 'pollHeaders["X-Session-Id"] = sessionId;' in source
    assert re.search(
        r"pollAsyncJob\(\s*config,\s*enqueued\.job_id,\s*uploadResult\.session_id\s*\)",
        source,
    )


def test_multipart_asset_uses_resume_introspection_and_persistent_state() -> (
    None
):
    source = _file_transfer_asset_source()

    assert "function multipartStateStorageKey(config, file)" in source
    assert 'String(sessionId || "")' not in source
    assert "var storageKey = multipartStateStorageKey(config, file);" in source
    assert "storageKey = multipartStateStorageKey(config, file);" in source
    assert (
        "window.localStorage.setItem(storageKey, JSON.stringify(state));"
        in source
    )
    assert 'base + "/uploads/introspect"' in source
    assert "window.localStorage.removeItem(storageKey);" in source


def test_multipart_asset_uses_progressive_sign_batch_default() -> None:
    source = _file_transfer_asset_source()

    assert 'root.dataset.signBatchSize || ""' in source
    assert re.search(
        r"Math\.min\(16,\s*Math\.max\(1,\s*maxConcurrency \* 2\)\)",
        source,
    )


def test_file_transfer_asset_uses_progressive_sign_batches() -> None:
    source = _file_transfer_asset_source()

    assert 'root.dataset.signBatchSize || ""' in source
    assert "Math.min(16, Math.max(1, maxConcurrency * 2))" in source
