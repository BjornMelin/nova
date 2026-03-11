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


def _extract_function(source: str, function_name: str) -> str:
    marker = f"function {function_name}("
    start_index = source.find(marker)
    assert start_index != -1
    brace_start = source.find("{", start_index)
    assert brace_start != -1
    depth = 0
    for idx in range(brace_start, len(source)):
        char = source[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start_index : idx + 1]
    raise AssertionError(f"failed to parse function body for {function_name}")


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
    key_helper_source = _extract_function(source, "multipartStateStorageKey")
    load_helper_source = _extract_function(source, "loadMultipartState")
    persist_helper_source = _extract_function(source, "persistMultipartState")
    clear_helper_source = _extract_function(source, "clearMultipartState")

    assert "function multipartStateStorageKey(config, file)" in source
    assert 'String(sessionId || "")' not in key_helper_source
    assert "var storageKey = multipartStateStorageKey(config, file);" in source
    assert "storageKey = multipartStateStorageKey(config, file);" in source
    assert "storage.setItem(storageKey, JSON.stringify(state));" in (
        persist_helper_source
    )
    assert 'base + "/uploads/introspect"' in source
    assert "storage.removeItem(storageKey);" in clear_helper_source
    assert "var storage = window.localStorage;" in load_helper_source


def test_multipart_asset_uses_progressive_sign_batch_default() -> None:
    source = _file_transfer_asset_source()

    assert 'root.dataset.signBatchSize || ""' in source
    assert re.search(
        r"Math\.min\(16,\s*Math\.max\(1,\s*maxConcurrency \* 2\)\)",
        source,
    )


def test_file_transfer_asset_uses_progressive_sign_batches_override() -> None:
    source = _file_transfer_asset_source()

    assert 'configuredBatchSize > 0' in source
    assert 'configuredBatchSize' in source