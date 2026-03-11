"""Download and extract a named GitHub Actions artifact from a workflow run."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

_GITHUB_API_BASE = "https://api.github.com"
_REQUEST_TIMEOUT_SECONDS = 30
_COPY_CHUNK_SIZE = 1024 * 1024
_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
_ARTIFACTS_PER_PAGE = 100


def _request_json(*, url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "nova-release-artifact-downloader",
        },
    )
    with urllib.request.urlopen(
        request,
        timeout=_REQUEST_TIMEOUT_SECONDS,
    ) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("GitHub API returned a non-object JSON payload")
    return payload


def _download_archive_to_tempfile(*, url: str, token: str) -> Path:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "nova-release-artifact-downloader",
        },
    )
    with tempfile.NamedTemporaryFile(
        prefix="nova-release-artifact-",
        suffix=".zip",
        delete=False,
    ) as handle:
        archive_path = Path(handle.name)
        try:
            with urllib.request.urlopen(
                request,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            ) as response:
                total_bytes = 0
                while True:
                    chunk = response.read(_COPY_CHUNK_SIZE)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > _MAX_ARCHIVE_BYTES:
                        raise RuntimeError(
                            "Artifact archive exceeds maximum allowed size"
                        )
                    handle.write(chunk)
        except Exception:
            archive_path.unlink(missing_ok=True)
            raise
    return archive_path


def _safe_archive_members(
    archive: zipfile.ZipFile,
) -> list[zipfile.ZipInfo]:
    members: list[zipfile.ZipInfo] = []
    total_uncompressed_bytes = 0
    for member in archive.infolist():
        member_path = Path(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise RuntimeError("Artifact archive contains unsafe path entry")
        if not member.filename.strip():
            raise RuntimeError("Artifact archive contains an empty path entry")
        unix_mode = member.external_attr >> 16
        if stat.S_ISLNK(unix_mode):
            raise RuntimeError("Artifact archive contains symlink entry")
        if member.is_dir():
            members.append(member)
            continue
        total_uncompressed_bytes += member.file_size
        if total_uncompressed_bytes > _MAX_UNCOMPRESSED_BYTES:
            raise RuntimeError(
                "Artifact archive exceeds maximum uncompressed size"
            )
        members.append(member)
    return members


def _extract_archive(*, archive_path: Path, output_dir: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        for member in _safe_archive_members(archive):
            destination = output_dir / member.filename
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with (
                archive.open(member) as source,
                destination.open("wb") as target,
            ):
                shutil.copyfileobj(source, target, length=_COPY_CHUNK_SIZE)


def _clear_directory_contents(path: Path) -> None:
    """Remove all children under an existing directory."""
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)


def _copy_directory_contents(*, source_dir: Path, target_dir: Path) -> None:
    """Copy all files/directories from source_dir into target_dir."""
    for item in source_dir.iterdir():
        destination = target_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)


def _artifact_listing_url(
    *,
    repo: str,
    run_id: int,
    artifact_name: str,
    page: int,
) -> str:
    query = urllib.parse.urlencode(
        {
            "name": artifact_name,
            "per_page": _ARTIFACTS_PER_PAGE,
            "page": page,
        }
    )
    return (
        f"{_GITHUB_API_BASE}/repos/{repo}/actions/runs/{run_id}/artifacts"
        f"?{query}"
    )


def _find_named_artifact(
    *,
    repo: str,
    run_id: int,
    artifact_name: str,
    token: str,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    page = 1
    total_count: int | None = None
    while True:
        listing = _request_json(
            url=_artifact_listing_url(
                repo=repo,
                run_id=run_id,
                artifact_name=artifact_name,
                page=page,
            ),
            token=token,
        )
        if total_count is None:
            raw_total_count = listing.get("total_count")
            if isinstance(raw_total_count, int) and raw_total_count >= 0:
                total_count = raw_total_count
        artifacts = listing.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise TypeError("GitHub API returned invalid artifacts payload")
        typed_artifacts = [item for item in artifacts if isinstance(item, dict)]
        matches.extend(
            item
            for item in typed_artifacts
            if item.get("name") == artifact_name
        )
        if (
            total_count is not None
            and page * _ARTIFACTS_PER_PAGE >= total_count
        ):
            break
        if len(typed_artifacts) < _ARTIFACTS_PER_PAGE:
            break
        page += 1

    if not matches:
        raise RuntimeError(
            f"Artifact {artifact_name!r} not found for run {run_id}"
        )

    active_matches = [
        item for item in matches if item.get("expired") is not True
    ]
    if len(active_matches) > 1:
        raise RuntimeError(
            f"Artifact {artifact_name!r} is ambiguous for run {run_id}"
        )
    if active_matches:
        return active_matches[0]

    raise RuntimeError(
        f"Artifact {artifact_name!r} for run {run_id} is expired"
    )


def download_run_artifact(
    *,
    repo: str,
    run_id: int,
    artifact_name: str,
    output_dir: Path,
    token: str,
) -> None:
    """Download and extract a named artifact from a workflow run.

    Args:
        repo: GitHub repository in ``owner/repo`` form.
        run_id: Workflow run identifier containing the artifact.
        artifact_name: Artifact name to download from the workflow run.
        output_dir: Destination directory for the extracted artifact contents.
        token: GitHub API token with read access to Actions artifacts.

    Returns:
        None.

    Raises:
        RuntimeError: If the artifact lookup, download, or extraction fails.
    """
    try:
        artifact = _find_named_artifact(
            repo=repo,
            run_id=run_id,
            artifact_name=artifact_name,
            token=token,
        )
        artifact_size = artifact.get("size_in_bytes")
        if (
            isinstance(artifact_size, int)
            and artifact_size > _MAX_ARCHIVE_BYTES
        ):
            raise RuntimeError(
                "Artifact "
                f"{artifact_name!r} for run {run_id} exceeds size limit"
            )

        archive_url = artifact.get("archive_download_url")
        if not isinstance(archive_url, str) or not archive_url:
            raise RuntimeError(
                "Artifact "
                f"{artifact_name!r} for run {run_id} has no download URL"
            )

        archive_path = _download_archive_to_tempfile(
            url=archive_url,
            token=token,
        )
        if output_dir.is_symlink():
            raise RuntimeError(
                f"output directory must not be a symlink: {output_dir}"
            )
        if output_dir.exists() and not output_dir.is_dir():
            raise RuntimeError(
                f"output directory exists and is not a directory: {output_dir}"
            )
        try:
            with tempfile.TemporaryDirectory(
                prefix="nova-release-artifact-extract-"
            ) as staging:
                staging_dir = Path(staging)
                _extract_archive(
                    archive_path=archive_path,
                    output_dir=staging_dir,
                )
                output_dir.mkdir(parents=True, exist_ok=True)
                _clear_directory_contents(output_dir)
                _copy_directory_contents(
                    source_dir=staging_dir,
                    target_dir=output_dir,
                )
        finally:
            archive_path.unlink(missing_ok=True)
    except TypeError as exc:
        raise RuntimeError(
            "GitHub API returned invalid artifact payload shape"
        ) from exc
    except (
        OSError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        zipfile.BadZipFile,
    ) as exc:
        raise RuntimeError(
            "Failed to download or extract artifact "
            f"{artifact_name!r} for run {run_id}"
        ) from exc


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a named artifact from a GitHub Actions run."
    )
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    token = (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_API_TOKEN")
    )
    if not token:
        raise SystemExit(
            "GITHUB_TOKEN, GH_TOKEN, or GITHUB_API_TOKEN is required"
        )
    try:
        download_run_artifact(
            repo=args.repo,
            run_id=args.run_id,
            artifact_name=args.artifact_name,
            output_dir=args.output_dir,
            token=token,
        )
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"GitHub artifact download failed with HTTP {exc.code}"
        ) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
