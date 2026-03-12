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
    idx = brace_start
    in_single = False
    in_double = False
    in_template = False
    in_line_comment = False
    in_block_comment = False
    escaped = False
    while idx < len(source):
        char = source[idx]
        next_char = source[idx + 1] if idx + 1 < len(source) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            idx += 1
            continue
        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                idx += 2
                continue
            idx += 1
            continue
        if in_single:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "'":
                in_single = False
            idx += 1
            continue
        if in_double:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_double = False
            idx += 1
            continue
        if in_template:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "`":
                in_template = False
            idx += 1
            continue

        if char == "/" and next_char == "/":
            in_line_comment = True
            idx += 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            idx += 2
            continue
        if char == "'":
            in_single = True
            idx += 1
            continue
        if char == '"':
            in_double = True
            idx += 1
            continue
        if char == "`":
            in_template = True
            idx += 1
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start_index : idx + 1]
        idx += 1
    raise AssertionError(f"failed to parse function body for {function_name}")


def test_poll_async_job_forwards_session_scope_header() -> None:
    source = _file_transfer_asset_source()

    assert "async function pollAsyncJob(config, jobId, sessionId)" in source
    assert 'pollHeaders["X-Session-Id"] = sessionId;' in source
    assert re.search(
        r"pollAsyncJob\(\s*config,\s*enqueued\.job_id,\s*uploadResult\.session_id\s*\)",
        source,
    )


def test_multipart_asset_uses_resume_introspection_state() -> None:
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
    assert 'config.transfersEndpointBase + "/downloads/presign"' in source
    assert "multipart upload completion is ambiguous" in source
    assert "var resumeMissingMultipart =" in source
    assert re.search(
        (
            r"if \(resumeMissingMultipart\)\s*\{[\s\S]*"
            r"clearMultipartState\(storageKey\);[\s\S]*"
            r"config\.transfersEndpointBase \+ \"/uploads/initiate\""
        ),
        source,
    )
    assert re.search(
        (
            r"else\s*\{[\s\S]*"
            r"throw error;\s*\}"
        ),
        source,
    )
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

    assert "configuredBatchSize > 0" in source
    assert "configuredBatchSize" in source
