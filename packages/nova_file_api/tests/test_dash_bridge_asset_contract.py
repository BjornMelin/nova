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
