from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.release.publish_workflow_api_tags import (
    latest_release_tag_for_major,
    publish_workflow_api_tags,
    workflow_api_changed,
)


def _run(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _run(repo_root, "init")
    _run(repo_root, "config", "user.name", "Nova Tests")
    _run(repo_root, "config", "user.email", "nova@example.com")
    return repo_root


def _commit_file(
    repo_root: Path,
    rel_path: str,
    content: str,
    message: str,
) -> str:
    path = repo_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _run(repo_root, "add", rel_path)
    _run(repo_root, "commit", "-m", message)
    return _run(repo_root, "rev-parse", "HEAD")


def test_workflow_api_changed_matches_public_surface_paths() -> None:
    assert workflow_api_changed(["docs/clients/dash-minimal-workflow.yml"])
    assert workflow_api_changed(
        [".github/workflows/reusable-post-deploy-validate.yml"]
    )
    assert not workflow_api_changed(
        ["packages/nova_file_api/src/nova_file_api/app.py"]
    )


def test_publish_workflow_api_tags_skips_when_surface_unchanged(
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    base_commit = _commit_file(
        repo_root,
        "packages/nova_file_api/src/nova_file_api/app.py",
        "print('base')\n",
        "chore: initial runtime commit",
    )
    head_commit = _commit_file(
        repo_root,
        "packages/nova_file_api/src/nova_file_api/app.py",
        "print('updated')\n",
        "fix: runtime only change",
    )

    payload = publish_workflow_api_tags(
        repo_root=repo_root,
        base_commit=base_commit,
        head_commit=head_commit,
        workflow_api_major=1,
        push=False,
        remote="origin",
    )

    assert payload["published"] is False
    assert payload["reason"] == "no_workflow_api_changes"
    assert latest_release_tag_for_major(repo_root, 1) is None


def test_publish_workflow_api_tags_creates_patch_release_and_major_tags(
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    base_commit = _commit_file(
        repo_root,
        ".github/workflows/reusable-post-deploy-validate.yml",
        "name: base\n",
        "chore: seed reusable workflow",
    )
    _run(
        repo_root,
        "tag",
        "-a",
        "v1.2.3",
        "-m",
        "Nova reusable workflow API v1.2.3",
    )
    head_commit = _commit_file(
        repo_root,
        ".github/workflows/reusable-post-deploy-validate.yml",
        "name: updated\n",
        "fix(workflow): tighten reusable contract",
    )

    payload = publish_workflow_api_tags(
        repo_root=repo_root,
        base_commit=base_commit,
        head_commit=head_commit,
        workflow_api_major=1,
        push=False,
        remote="origin",
    )

    assert payload["published"] is True
    assert payload["bump"] == "patch"
    assert payload["previous_release_tag"] == "v1.2.3"
    assert payload["release_tag"] == "v1.2.4"
    assert payload["major_tag"] == "v1"
    assert (
        _run(repo_root, "rev-parse", "refs/tags/v1.2.4^{commit}") == head_commit
    )
    assert _run(repo_root, "rev-parse", "refs/tags/v1^{commit}") == head_commit


def test_publish_workflow_api_tags_requires_new_major_for_breaking_changes(
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    base_commit = _commit_file(
        repo_root,
        "docs/clients/post-deploy-validation-integration-guide.md",
        "base\n",
        "chore: seed docs",
    )
    _run(
        repo_root,
        "tag",
        "-a",
        "v1.2.3",
        "-m",
        "Nova reusable workflow API v1.2.3",
    )
    head_commit = _commit_file(
        repo_root,
        "docs/clients/post-deploy-validation-integration-guide.md",
        "breaking\n",
        "feat(workflow)!: break reusable contract",
    )

    with pytest.raises(ValueError, match="workflow_api_major"):
        publish_workflow_api_tags(
            repo_root=repo_root,
            base_commit=base_commit,
            head_commit=head_commit,
            workflow_api_major=1,
            push=False,
            remote="origin",
        )


def test_publish_workflow_api_tags_can_start_new_major_channel(
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    base_commit = _commit_file(
        repo_root,
        "docs/clients/post-deploy-validation-integration-guide.md",
        "base\n",
        "chore: seed docs",
    )
    _run(
        repo_root,
        "tag",
        "-a",
        "v1.2.3",
        "-m",
        "Nova reusable workflow API v1.2.3",
    )
    head_commit = _commit_file(
        repo_root,
        "docs/clients/post-deploy-validation-integration-guide.md",
        "breaking\n",
        "feat(workflow)!: publish v2 contract",
    )

    payload = publish_workflow_api_tags(
        repo_root=repo_root,
        base_commit=base_commit,
        head_commit=head_commit,
        workflow_api_major=2,
        push=False,
        remote="origin",
    )

    assert payload["published"] is True
    assert payload["release_tag"] == "v2.0.0"
    assert payload["major_tag"] == "v2"
    assert (
        _run(repo_root, "rev-parse", "refs/tags/v2.0.0^{commit}") == head_commit
    )
    assert _run(repo_root, "rev-parse", "refs/tags/v2^{commit}") == head_commit
