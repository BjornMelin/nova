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


def _dash_integration_source() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    module_path = (
        repo_root
        / "packages"
        / "nova_dash_bridge"
        / "src"
        / "nova_dash_bridge"
        / "dash_integration.py"
    )
    return module_path.read_text(encoding="utf-8")


def test_poll_async_job_forwards_session_scope_header() -> None:
    source = _file_transfer_asset_source()

    assert "async function pollAsyncJob(config, jobId, sessionId)" in source
    assert 'pollHeaders["X-Session-Id"] = sessionId;' in source
    assert re.search(
        r"pollAsyncJob\(\s*config,\s*enqueued\.job_id,\s*uploadResult\.session_id\s*\)",
        source,
    )


def test_upload_result_contract_includes_etag_and_version_id() -> None:
    source = _file_transfer_asset_source()

    assert "function requireUploadEtag(etag)" in source
    assert 'throw new Error("upload completed without an ETag")' in source
    assert (
        "etag: requireUploadEtag(uploadMetadata && uploadMetadata.etag)"
        in source
    )
    assert "version_id: normalizeOptionalString(" in source
    assert re.search(
        (
            r"var singleEtag = await putObject\("
            r"initiated\.url,\s*file,\s*contentType\);"
        ),
        source,
    )
    assert re.search(
        r"var multipartResult = await uploadMultipart\(",
        source,
    )
    assert re.search(
        r"var completedUpload = await postJson\(base \+ \"/uploads/complete\",",
        source,
    )


def test_async_job_defaults_and_result_contract_are_canonical() -> None:
    asset_source = _file_transfer_asset_source()
    dash_source = _dash_integration_source()

    assert "async_job_type: str = TRANSFER_PROCESS_JOB_TYPE" in dash_source
    assert (
        'asyncJobType: root.dataset.asyncJobType || "transfer.process"'
        in asset_source
    )
    assert "job_type: config.asyncJobType," in asset_source
    assert (
        'if (typeof result.export_key !== "string" || !result.export_key)'
        in asset_source
    )
    assert "requestPayload.filename = result.download_filename;" in asset_source
