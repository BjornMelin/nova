"""Publish versioned tags for Nova reusable workflow APIs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import common

WORKFLOW_API_PATH_PREFIXES = (
    ".github/actions/",
    ".github/workflows/reusable-",
    "docs/clients/",
    "docs/contracts/",
    "tests/infra/test_workflow_contract_docs.py",
    "tests/infra/test_docs_authority_contracts.py",
    "tests/infra/test_release_workflow_contracts.py",
    "tests/infra/test_workflow_productization_contracts.py",
)

WORKFLOW_API_EXACT_PATHS = {
    "README.md",
    "docs/PRD.md",
    "docs/architecture/requirements.md",
    (
        "docs/architecture/adr/"
        "ADR-0027-hard-cut-downstream-integration-and-consumer-contract-enforcement.md"
    ),
    (
        "docs/architecture/adr/"
        "ADR-0028-auth0-tenant-ops-reusable-workflow-api-contract.md"
    ),
    (
        "docs/architecture/adr/"
        "ADR-0031-reusable-github-workflow-api-and-versioning-policy-for-deployment-automation.md"
    ),
    (
        "docs/architecture/spec/"
        "SPEC-0021-downstream-hard-cut-integration-and-consumer-validation-contract.md"
    ),
    (
        "docs/architecture/spec/"
        "SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md"
    ),
    (
        "docs/architecture/spec/"
        "SPEC-0025-reusable-workflow-integration-contract.md"
    ),
    "docs/plan/release/AUTH0-A0DEPLOY-RUNBOOK.md",
    "docs/plan/release/RELEASE-POLICY.md",
    "docs/plan/release/RELEASE-RUNBOOK.md",
    "docs/plan/release/github-actions-secrets-and-vars-setup-guide.md",
    "docs/plan/release/config-values-reference-guide.md",
}


def workflow_api_changed(changed_files: list[str]) -> bool:
    """Return whether the release touched the public workflow API surface."""
    for path in changed_files:
        if path in WORKFLOW_API_EXACT_PATHS:
            return True
        if any(
            path.startswith(prefix) for prefix in WORKFLOW_API_PATH_PREFIXES
        ):
            return True
    return False


def _resolve_tag_commit(repo_root: Path, tag: str) -> str | None:
    """Return the commit a tag resolves to, or None when absent."""
    try:
        return common.run_git(
            repo_root,
            ["rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
        )
    except RuntimeError:
        return None


def latest_release_tag_for_major(repo_root: Path, major: int) -> str | None:
    """Return the latest immutable release tag for a workflow major line."""
    output = common.run_git(
        repo_root,
        ["tag", "--list", f"v{major}.*.*", "--sort=-version:refname"],
    )
    for line in output.splitlines():
        tag = line.strip()
        if tag:
            return tag
    return None


def _parse_release_tag(tag: str) -> tuple[int, int, int]:
    """Parse a repo release tag in v<major>.<minor>.<patch> form."""
    if not tag.startswith("v"):
        raise ValueError(f"invalid release tag: {tag}")
    try:
        major_text, minor_text, patch_text = tag[1:].split(".")
        return int(major_text), int(minor_text), int(patch_text)
    except ValueError as exc:
        raise ValueError(f"invalid release tag: {tag}") from exc


def next_release_tag(
    *,
    repo_root: Path,
    workflow_api_major: int,
    bump: common.BumpLevel,
) -> tuple[str, str | None]:
    """Compute the next immutable release tag for a workflow major line."""
    latest_tag = latest_release_tag_for_major(repo_root, workflow_api_major)
    if latest_tag is None:
        return f"v{workflow_api_major}.0.0", None

    current_major, _minor, _patch = _parse_release_tag(latest_tag)
    if current_major != workflow_api_major:
        raise ValueError(
            "latest release tag major does not match requested "
            f"workflow_api_major={workflow_api_major}"
        )
    if bump == "major":
        raise ValueError(
            "workflow API change requires a new major channel; "
            f"set workflow_api_major to {workflow_api_major + 1} before "
            "publishing breaking reusable-workflow changes"
        )
    return f"v{common.increment_semver(latest_tag[1:], bump)}", latest_tag


def _create_or_verify_annotated_tag(
    *,
    repo_root: Path,
    tag: str,
    commit_sha: str,
    message: str,
    force: bool,
) -> None:
    """Create an annotated tag, or verify an existing tag target."""
    existing_commit = _resolve_tag_commit(repo_root, tag)
    if (
        existing_commit is not None
        and existing_commit == commit_sha
        and not force
    ):
        return
    if (
        existing_commit is not None
        and existing_commit != commit_sha
        and not force
    ):
        raise ValueError(
            f"tag {tag} already exists at {existing_commit}, not {commit_sha}"
        )
    args = ["tag", "-a", tag, commit_sha, "-m", message]
    if force:
        args.insert(1, "-f")
    common.run_git(repo_root, args)


def publish_workflow_api_tags(
    *,
    repo_root: Path,
    base_commit: str | None,
    head_commit: str,
    workflow_api_major: int,
    push: bool,
    remote: str,
) -> dict[str, Any]:
    """Publish immutable and moving major tags for workflow API changes."""
    changed_files = common.list_changed_files(
        repo_root,
        head_commit=head_commit,
        base_commit=base_commit,
    )
    if not workflow_api_changed(changed_files):
        return {
            "published": False,
            "reason": "no_workflow_api_changes",
            "workflow_api_major": workflow_api_major,
            "release_commit_sha": head_commit,
            "changed_files": changed_files,
        }

    commit_messages = common.collect_commit_messages(
        repo_root,
        head_commit=head_commit,
        base_commit=base_commit,
    )
    bump = common.determine_bump_level(commit_messages)
    release_tag, previous_release_tag = next_release_tag(
        repo_root=repo_root,
        workflow_api_major=workflow_api_major,
        bump=bump,
    )
    major_tag = f"v{workflow_api_major}"

    _create_or_verify_annotated_tag(
        repo_root=repo_root,
        tag=release_tag,
        commit_sha=head_commit,
        message=f"Nova reusable workflow API {release_tag}",
        force=False,
    )
    _create_or_verify_annotated_tag(
        repo_root=repo_root,
        tag=major_tag,
        commit_sha=head_commit,
        message=f"Nova reusable workflow API {major_tag}",
        force=True,
    )

    if push:
        common.run_git(repo_root, ["push", remote, f"refs/tags/{release_tag}"])
        common.run_git(
            repo_root,
            ["push", remote, f"refs/tags/{major_tag}", "--force"],
        )

    return {
        "published": True,
        "workflow_api_major": workflow_api_major,
        "bump": bump,
        "previous_release_tag": previous_release_tag,
        "release_tag": release_tag,
        "major_tag": major_tag,
        "release_commit_sha": head_commit,
        "changed_files": changed_files,
        "pushed": push,
        "remote": remote,
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-commit")
    parser.add_argument("--head-commit", default="HEAD")
    parser.add_argument("--workflow-api-major", type=int, default=1)
    parser.add_argument(
        "--metadata-path",
        default=".artifacts/workflow-api-tagging.json",
    )
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--push", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Publish reusable-workflow tags and write metadata output."""
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    head_commit = common.run_git(
        repo_root,
        ["rev-parse", "--verify", args.head_commit],
    )
    payload = publish_workflow_api_tags(
        repo_root=repo_root,
        base_commit=args.base_commit,
        head_commit=head_commit,
        workflow_api_major=args.workflow_api_major,
        push=bool(args.push),
        remote=str(args.remote),
    )

    metadata_path = Path(args.metadata_path)
    if not metadata_path.is_absolute():
        metadata_path = repo_root / metadata_path
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"workflow-api-tagging: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
