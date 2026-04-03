"""Prepare one human-authored release PR from the current repository state."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from scripts.release import (
    apply_versions,
    changed_units,
    common,
    release_paths,
    release_prep,
    version_plan,
    write_manifest,
)


def _run_uv_lock(repo_root: Path) -> None:
    """Refresh ``uv.lock`` from the repository root."""
    uv_path = _require_uv_available()
    subprocess.run(  # noqa: S603
        [uv_path, "lock"],
        check=True,
        cwd=repo_root,
        text=True,
    )


def _require_uv_available() -> str:
    """Return the uv executable path or raise a clear contract error."""
    uv_path = shutil.which("uv")
    if uv_path is None:
        raise RuntimeError("uv executable not found on PATH")
    return uv_path


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for release prep.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--manifest-path",
        default=release_paths.RELEASE_VERSION_MANIFEST_PATH,
    )
    parser.add_argument(
        "--release-prep-path",
        default=release_paths.RELEASE_PREP_PATH,
    )
    parser.add_argument("--force-bump", choices=["major", "minor", "patch"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-lock", action="store_true")
    return parser.parse_args()


def _display_path(path: Path, *, repo_root: Path) -> str:
    """Render one path relative to repo_root when possible."""
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def main() -> int:
    """Generate committed release-prep artifacts and apply planned versions.

    Returns:
        Process exit code where 0 means success.
    """
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    units = common.load_workspace_units(repo_root)

    manifest_path = Path(args.manifest_path)
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path
    release_prep_path = Path(args.release_prep_path)
    if not release_prep_path.is_absolute():
        release_prep_path = repo_root / release_prep_path

    head_commit = common.run_git(repo_root, ["rev-parse", "HEAD"])
    base_commit = common.find_manifest_base_commit(
        repo_root,
        manifest_path=str(manifest_path),
    )
    first_release = base_commit is None
    changed_files = common.list_changed_files(
        repo_root,
        head_commit=head_commit,
        base_commit=base_commit,
    )
    changed_report = changed_units.build_changed_units_report(
        units=units,
        changed_files=changed_files,
        base_commit=base_commit,
        head_commit=head_commit,
        first_release=first_release,
    )
    commit_messages = common.collect_commit_messages(
        repo_root,
        base_commit=base_commit,
        head_commit=head_commit,
    )
    planned_versions = version_plan.build_version_plan(
        units=units,
        changed_report=changed_report,
        commit_messages=commit_messages,
        forced_bump=args.force_bump,
    )

    if args.dry_run:
        print(
            "release-prep: "
            f"changed_units={len(changed_report['changed_units'])} "
            f"planned_units={len(planned_versions['units'])} dry_run=true"
        )
        return 0

    if not args.skip_lock:
        _require_uv_available()

    apply_versions.apply_version_updates(
        repo_root=repo_root,
        version_plan=planned_versions,
        units=units,
        dry_run=False,
    )

    if not args.skip_lock:
        _run_uv_lock(repo_root)

    refreshed_units = common.load_workspace_units(repo_root)
    manifest_text = write_manifest.render_manifest(
        units=refreshed_units,
        changed_report=changed_report,
        version_plan=planned_versions,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest_text, encoding="utf-8")

    release_prep_payload = release_prep.build_release_prep(
        prepared_from_commit=head_commit,
        prepared_at=common.iso_timestamp(),
        changed_report=changed_report,
        version_plan=planned_versions,
    )
    common.write_json(release_prep_path, release_prep_payload)

    print(
        "release-prep: "
        f"changed_units={len(changed_report['changed_units'])} "
        f"planned_units={len(planned_versions['units'])} "
        f"manifest={_display_path(manifest_path, repo_root=repo_root)} "
        f"release_prep={_display_path(release_prep_path, repo_root=repo_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
