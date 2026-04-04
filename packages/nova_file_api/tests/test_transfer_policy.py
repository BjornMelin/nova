from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from nova_file_api.transfer_config import TransferConfig
from nova_file_api.transfer_policy import (
    AppConfigTransferPolicyProvider,
    AppConfigTransferPolicySource,
    build_transfer_policy_provider,
    resolve_transfer_policy,
    resolve_transfer_policy_document,
)
from nova_runtime_support.transfer_policy_document import TransferPolicyDocument


class _StubAppConfigClient:
    def __init__(self) -> None:
        self.start_calls = 0
        self.poll_calls = 0
        self.last_poll_cursor = ""

    async def start_configuration_session(
        self,
        **_: object,
    ) -> dict[str, object]:
        self.start_calls += 1
        return {"InitialConfigurationToken": "token-1"}

    async def get_latest_configuration(self, **_: object) -> dict[str, object]:
        self.poll_calls += 1
        if self.poll_calls == 1:
            configuration = (
                b'{"policy_id":"remote-tier","max_concurrency_hint":8,'
                b'"active_multipart_upload_limit":400,'
                b'"daily_ingress_budget_bytes":2199023255552,'
                b'"sign_requests_per_upload_limit":1024}'
            )
            poll_cursor = "cursor-2"
        else:
            configuration = (
                b'{"policy_id":"remote-tier-tight","max_concurrency_hint":2,'
                b'"active_multipart_upload_limit":8,'
                b'"daily_ingress_budget_bytes":1099511627776,'
                b'"sign_requests_per_upload_limit":128}'
            )
            poll_cursor = "cursor-3"
        self.last_poll_cursor = poll_cursor
        return {
            "Configuration": configuration,
            "NextPollConfigurationToken": poll_cursor,
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
        checksum_mode="none",
        upload_sessions_table="upload-sessions",
        usage_table="transfer-usage",
        large_export_worker_threshold_bytes=50 * 1024 * 1024 * 1024,
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


@pytest.mark.anyio
async def test_appconfig_source_refreshes_again_after_poll_window_expires() -> (
    None
):
    client = _StubAppConfigClient()
    source = AppConfigTransferPolicySource(
        client=client,
        application_identifier=" app ",
        environment_identifier=" env ",
        configuration_profile_identifier=" profile ",
        minimum_poll_interval_seconds=60,
    )

    first = await resolve_transfer_policy_document(source=source)
    assert first is not None
    assert first.max_concurrency_hint == 8

    source._next_refresh_at = datetime(1970, 1, 1, tzinfo=UTC)
    second = await resolve_transfer_policy_document(source=source)
    policy = resolve_transfer_policy(config=_config(), document=second)

    assert second is not None
    assert second.policy_id == "remote-tier-tight"
    assert second.max_concurrency_hint == 2
    assert policy.max_concurrency_hint == 2
    assert policy.active_multipart_upload_limit == 8
    assert policy.daily_ingress_budget_bytes == 1099511627776
    assert policy.sign_requests_per_upload_limit == 128
    assert client.start_calls == 1
    assert client.poll_calls == 2
    assert source._token == client.last_poll_cursor


@pytest.mark.anyio
async def test_build_provider_strips_appconfig_ids() -> None:
    provider = build_transfer_policy_provider(
        config=replace(
            _config(),
            policy_appconfig_application=" app ",
            policy_appconfig_environment=" env ",
            policy_appconfig_profile=" profile ",
        ),
        appconfig_client=_StubAppConfigClient(),
    )

    assert isinstance(provider, AppConfigTransferPolicyProvider)
    assert provider.source.application_identifier == "app"
    assert provider.source.environment_identifier == "env"
    assert provider.source.configuration_profile_identifier == "profile"


@pytest.mark.anyio
async def test_resolve_transfer_policy_selects_profile_by_hint() -> None:
    document = {
        "policy_id": "default",
        "profiles": {
            "remote": {
                "policy_id": "remote",
                "max_concurrency_hint": 8,
                "sign_batch_size_hint": 64,
                "accelerate_enabled": True,
                "checksum_mode": "optional",
                "large_export_worker_threshold_bytes": 25 * 1024 * 1024 * 1024,
            }
        },
    }

    provider = AppConfigTransferPolicyProvider(
        config=_config(),
        source=AppConfigTransferPolicySource(
            client=_StubAppConfigClient(),
            application_identifier="app",
            environment_identifier="env",
            configuration_profile_identifier="profile",
            minimum_poll_interval_seconds=60,
        ),
    )
    provider.source._cached_document = TransferPolicyDocument.model_validate(
        document
    )
    provider.source._next_refresh_at = datetime.max.replace(tzinfo=UTC)

    policy = await provider.resolve(
        scope_id="scope-1",
        policy_hint="remote",
        checksum_preference="standard",
    )

    assert policy.policy_id == "remote"
    assert policy.accelerate_enabled is True
    assert policy.checksum_mode == "optional"
    assert policy.large_export_worker_threshold_bytes == 25 * 1024 * 1024 * 1024


def test_strict_checksum_preference_enables_supported_algorithm() -> None:
    policy = resolve_transfer_policy(
        config=_config(),
        checksum_preference="strict",
    )

    assert policy.checksum_mode == "required"
    assert policy.checksum_algorithm == "SHA256"


def test_checksum_mode_without_algorithm_defaults_to_sha256() -> None:
    policy = resolve_transfer_policy(
        config=_config(),
        document=TransferPolicyDocument(
            policy_id="checksum-tier",
            checksum_mode="optional",
        ),
    )

    assert policy.checksum_mode == "optional"
    assert policy.checksum_algorithm == "SHA256"
