from __future__ import annotations

import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from scripts.release import download_run_artifact as artifact_module
from scripts.release.download_run_artifact import (
    _extract_archive,
    _find_named_artifact,
    download_run_artifact,
)


def test_extract_archive_rejects_unsafe_member_paths(tmp_path: Path) -> None:
    archive_path = tmp_path / "artifact.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("../escape.txt", "bad")

    with pytest.raises(RuntimeError, match="unsafe path"):
        _extract_archive(
            archive_path=archive_path,
            output_dir=tmp_path / "out",
        )


def test_find_named_artifact_uses_name_filter_and_paginates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []

    def _fake_request_json(*, url: str, token: str) -> dict[str, object]:
        del token
        urls.append(url)
        page = parse_qs(urlparse(url).query)["page"][0]
        if page == "1":
            return {
                "total_count": 101,
                "artifacts": [
                    {
                        "id": index,
                        "name": "release-plan-artifacts",
                        "expired": True,
                    }
                    for index in range(100)
                ],
            }
        return {
            "total_count": 101,
            "artifacts": [
                {
                    "id": 999,
                    "name": "release-plan-artifacts",
                    "expired": False,
                    "archive_download_url": "https://example.local/archive.zip",
                }
            ],
        }

    monkeypatch.setattr(artifact_module, "_request_json", _fake_request_json)

    artifact = _find_named_artifact(
        repo="acme/nova",
        run_id=123,
        artifact_name="release-plan-artifacts",
        token="token",
    )

    assert artifact["id"] == 999
    assert len(urls) == 2
    assert "name=release-plan-artifacts" in urls[0]
    assert "per_page=100" in urls[0]
    assert "page=1" in urls[0]
    assert "page=2" in urls[1]


def test_find_named_artifact_rejects_ambiguous_active_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        artifact_module,
        "_request_json",
        lambda **_: {
            "total_count": 2,
            "artifacts": [
                {"id": 1, "name": "release-plan-artifacts", "expired": False},
                {"id": 2, "name": "release-plan-artifacts", "expired": False},
            ],
        },
    )

    with pytest.raises(RuntimeError, match="ambiguous"):
        _find_named_artifact(
            repo="acme/nova",
            run_id=123,
            artifact_name="release-plan-artifacts",
            token="token",
        )


def test_download_run_artifact_extracts_matching_archive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "artifact.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("release-apply-metadata.json", '{"ok": true}')

    monkeypatch.setattr(
        artifact_module,
        "_find_named_artifact",
        lambda **_: {
            "name": "release-apply-artifacts",
            "expired": False,
            "size_in_bytes": 128,
            "archive_download_url": "https://example.local/archive.zip",
        },
    )
    monkeypatch.setattr(
        artifact_module,
        "_download_archive_to_tempfile",
        lambda **_: archive_path,
    )

    output_dir = tmp_path / "out"
    download_run_artifact(
        repo="acme/nova",
        run_id=123,
        artifact_name="release-apply-artifacts",
        output_dir=output_dir,
        token="token",
    )

    assert (output_dir / "release-apply-metadata.json").read_text(
        encoding="utf-8"
    ) == '{"ok": true}'


def test_download_run_artifact_rejects_symlinked_output_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "artifact.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr("release-apply-metadata.json", '{"ok": true}')

    monkeypatch.setattr(
        artifact_module,
        "_find_named_artifact",
        lambda **_: {
            "name": "release-apply-artifacts",
            "expired": False,
            "size_in_bytes": 128,
            "archive_download_url": "https://example.local/archive.zip",
        },
    )
    monkeypatch.setattr(
        artifact_module,
        "_download_archive_to_tempfile",
        lambda **_: archive_path,
    )

    target_dir = tmp_path / "target"
    target_dir.mkdir()
    sentinel = target_dir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    output_dir = tmp_path / "out-link"
    output_dir.symlink_to(target_dir, target_is_directory=True)

    with pytest.raises(RuntimeError, match="must not be a symlink"):
        download_run_artifact(
            repo="acme/nova",
            run_id=123,
            artifact_name="release-apply-artifacts",
            output_dir=output_dir,
            token="token",
        )

    assert sentinel.read_text(encoding="utf-8") == "keep"
