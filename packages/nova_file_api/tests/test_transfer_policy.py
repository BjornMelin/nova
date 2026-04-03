from __future__ import annotations

import pytest

from nova_file_api.transfer_config import TransferConfig
from nova_file_api.transfer_policy import (
    AppConfigTransferPolicySource,
    resolve_transfer_policy,
    resolve_transfer_policy_document,
)


class _StubAppConfigClient:
    async def start_configuration_session(
        self,
        **_: object,
    ) -> dict[str, object]:
        return {"InitialConfigurationToken": "token-1"}

    async def get_latest_configuration(self, **_: object) -> dict[str, object]:
        return {
            "Configuration": (
                b'{"policy_id":"remote-tier","max_concurrency_hint":8,'
                b'"active_multipart_upload_limit":400,'
                b'"daily_ingress_budget_bytes":2199023255552,'
                b'"sign_requests_per_upload_limit":1024}'
            ),
            "NextPollConfigurationToken": "token-2",
            "NextPollIntervalInSeconds": 60,
        }


def _config() -> TransferConfig:
    return TransferConfig(
        enabled=True,
        bucket="bucket",
        upload_prefix="uploads/",
        export_prefix="exports/",
        tmp_prefix="tmp/",
        presign_upload_ttl_seconds=1800,
        presign_download_ttl_seconds=900,
        multipart_threshold_bytes=100 * 1024 * 1024,
        part_size_bytes=128 * 1024 * 1024,
        export_copy_part_size_bytes=2 * 1024 * 1024 * 1024,
        max_concurrency=4,
        export_copy_max_concurrency=8,
        target_upload_part_count=2000,
        use_accelerate_endpoint=False,
        max_upload_bytes=536_870_912_000,
        policy_id="default",
        policy_version="2026-04-03",
        active_multipart_upload_limit=200,
        daily_ingress_budget_bytes=1024 * 1024 * 1024 * 1024,
        sign_requests_per_upload_limit=512,
        resumable_window_seconds=7 * 24 * 60 * 60,
        checksum_algorithm=None,
        upload_sessions_table="upload-sessions",
        usage_table="transfer-usage",
        policy_appconfig_application="app",
        policy_appconfig_environment="env",
        policy_appconfig_profile="profile",
        policy_appconfig_poll_interval_seconds=60,
    )


@pytest.mark.anyio
async def test_resolve_transfer_policy_document_reads_appconfig_payload() -> (
    None
):
    source = AppConfigTransferPolicySource(
        client=_StubAppConfigClient(),
        application_identifier="app",
        environment_identifier="env",
        configuration_profile_identifier="profile",
        minimum_poll_interval_seconds=60,
    )

    document = await resolve_transfer_policy_document(source=source)

    assert document is not None
    assert document.policy_id == "remote-tier"
    assert document.max_concurrency_hint == 8


@pytest.mark.anyio
async def test_resolve_transfer_policy_applies_appconfig_overlay() -> None:
    source = AppConfigTransferPolicySource(
        client=_StubAppConfigClient(),
        application_identifier="app",
        environment_identifier="env",
        configuration_profile_identifier="profile",
        minimum_poll_interval_seconds=60,
    )
    document = await resolve_transfer_policy_document(source=source)

    policy = resolve_transfer_policy(config=_config(), document=document)

    assert policy.policy_id == "remote-tier"
    assert policy.max_concurrency_hint == 8
    assert policy.active_multipart_upload_limit == 200
    assert policy.daily_ingress_budget_bytes == 1024 * 1024 * 1024 * 1024
    assert policy.sign_requests_per_upload_limit == 512
