"""Infra contract tests for absorbed Nova templates.

These checks are deterministic and enforce policy/path invariants from
SPEC-0013/SPEC-0014.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_absorbed_template_paths_present() -> None:
    """Absorbed infra templates must exist under Nova-owned paths."""
    required_templates = [
        "infra/nova/nova-ci-cd.yml",
        "infra/nova/nova-codebuild-release.yml",
        "infra/nova/nova-iam-roles.yml",
        "infra/nova/deploy/image-digest-ssm.yml",
        "infra/runtime/ecr.yml",
        "infra/runtime/ecs/cluster.yml",
        "infra/runtime/ecs/service.yml",
        "infra/runtime/file_transfer/async.yml",
        "infra/runtime/file_transfer/cache.yml",
        "infra/runtime/file_transfer/s3.yml",
        "infra/runtime/file_transfer/worker.yml",
        "infra/runtime/kms.yml",
    ]

    missing = [
        path for path in required_templates if not (REPO_ROOT / path).is_file()
    ]
    assert not missing, f"Missing absorbed templates: {missing}"


def test_pipeline_single_source_contract() -> None:
    """Pipeline must use AppSourceOutput only."""
    text = _read("infra/nova/nova-ci-cd.yml")

    assert "InfraSourceOutput" not in text
    assert (
        "TemplatePath: AppSourceOutput::infra/nova/deploy/image-digest-ssm.yml"
        in text
    )

    expected_stage_order = [
        "- Name: Source",
        "- Name: Build",
        "- Name: DeployDev",
        "- Name: ValidateDev",
        "- Name: ManualApproval",
        "- Name: DeployProd",
        "- Name: ValidateProd",
    ]
    stage_positions = [text.find(stage) for stage in expected_stage_order]
    assert all(pos >= 0 for pos in stage_positions), (
        "Missing expected pipeline stage(s)"
    )
    assert stage_positions == sorted(stage_positions), (
        "Pipeline stage order contract drifted"
    )


def test_digest_marker_path_and_env_contracts() -> None:
    """Digest marker path and constraints must stay stable."""
    text = _read("infra/nova/deploy/image-digest-ssm.yml")

    assert (
        'Name: !Sub "/nova/${Environment}/${ServiceName}/image-digest"' in text
    )
    assert "AllowedValues:" in text and "- dev" in text and "- prod" in text
    assert 'AllowedPattern: "^sha256:[A-Fa-f0-9]{64}$"' in text


def test_iam_scope_constraints_for_release_roles() -> None:
    """Critical IAM constraints must remain tightly scoped."""
    text = _read("infra/nova/nova-iam-roles.yml")

    assert "token.actions.githubusercontent.com:aud: sts.amazonaws.com" in text
    assert (
        "repo:${RepositoryOwner}/${RepositoryName}:ref:refs/heads/${MainBranchName}"
        in text
    )

    passrole_blocks = re.findall(
        r"Action:\n\s*- iam:PassRole\n\s*Resource:(?:\n\s*- .*?)+",
        text,
        flags=re.MULTILINE,
    )
    assert passrole_blocks, "Expected iam:PassRole policy blocks"
    assert all(
        '"*"' not in block and '- "*"' not in block for block in passrole_blocks
    )

    assert "iam:PassedToService:" in text
    assert "ecs-tasks.amazonaws.com" in text


def test_runtime_env_and_parameter_contracts() -> None:
    """Runtime templates must preserve env/parameter guardrails."""
    async_text = _read("infra/runtime/file_transfer/async.yml")
    worker_text = _read("infra/runtime/file_transfer/worker.yml")
    service_text = _read("infra/runtime/ecs/service.yml")

    assert "JobsVisibilityTimeoutSeconds" in async_text
    assert "MinValue: 30" in async_text
    assert "JobsMessageRetentionSeconds" in async_text
    assert "MaxValue: 1209599" in async_text
    assert "SqsManagedSseEnabled: true" in async_text
    assert "PointInTimeRecoveryEnabled: true" in async_text

    for env_name in [
        "FILE_TRANSFER_JOBS_QUEUE_URL",
        "FILE_TRANSFER_JOBS_REGION",
        "FILE_TRANSFER_BUCKET",
        "FILE_TRANSFER_UPLOAD_PREFIX",
        "FILE_TRANSFER_EXPORT_PREFIX",
        "FILE_TRANSFER_TMP_PREFIX",
        "APP_SYNC_PROCESSING_MAX_BYTES",
    ]:
        assert f"- Name: {env_name}" in worker_text

    assert "FileTransferAsyncParamsProvided:" in service_text
    assert "FileTransferCacheParamsProvided:" in service_text
    assert (
        "FileTransferJobsQueueArn, FileTransferJobsTableArn, and"
        in service_text
    )
    assert (
        "FileTransferCacheSecurityGroupExportName is required" in service_text
    )
