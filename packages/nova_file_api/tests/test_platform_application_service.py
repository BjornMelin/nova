"""Unit tests for platform application-layer request orchestration."""

from __future__ import annotations

from typing import cast

import pytest

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.application.platform import PlatformApplicationService
from nova_file_api.config import Settings
from nova_file_api.errors import FileTransferError
from nova_file_api.models import Principal, ResourcePlanRequest
from nova_file_api.transfer import TransferService
from nova_runtime_support.metrics import MetricsCollector

from .support.doubles import StubTransferService


def _build_settings() -> Settings:
    settings = Settings.model_validate(
        {
            "APP_NAME": "nova-test",
            "APP_VERSION": "1.2.3",
            "ENVIRONMENT": "test",
            "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
            "OIDC_ISSUER": "https://issuer.example.com/",
            "OIDC_AUDIENCE": "api://nova",
            "OIDC_JWKS_URL": "https://issuer.example.com/.well-known/jwks.json",
        }
    )
    settings.exports_enabled = True
    settings.file_transfer_enabled = True
    return settings


def _build_service(
    *,
    settings: Settings | None = None,
    metrics: MetricsCollector | None = None,
    activity_store: MemoryActivityStore | None = None,
) -> PlatformApplicationService:
    return PlatformApplicationService(
        settings=_build_settings() if settings is None else settings,
        metrics=MetricsCollector(namespace="Tests")
        if metrics is None
        else metrics,
        transfer_service=cast(TransferService, StubTransferService()),
        activity_store=MemoryActivityStore()
        if activity_store is None
        else activity_store,
    )


@pytest.mark.anyio
async def test_get_capabilities_exposes_runtime_flags_and_policy() -> None:
    """Capability descriptors should match the resolved transfer policy."""
    service = _build_service()

    response = await service.get_capabilities()

    capabilities = {entry.key: entry for entry in response.capabilities}
    assert capabilities["exports"].enabled is True
    assert capabilities["exports.status.poll"].enabled is True
    assert capabilities["transfers"].enabled is True
    assert capabilities["transfers.policy"].enabled is True
    assert capabilities["transfers.policy"].details == {
        "policy_id": "default",
        "policy_version": "2026-04-03",
        "max_concurrency_hint": 4,
        "sign_batch_size_hint": 64,
        "target_upload_part_count": 2000,
        "minimum_part_size_bytes": 64 * 1024 * 1024,
        "maximum_part_size_bytes": 512 * 1024 * 1024,
        "accelerate_enabled": False,
        "checksum_algorithm": None,
        "checksum_mode": "none",
        "resumable_ttl_seconds": 7 * 24 * 60 * 60,
        "active_multipart_upload_limit": 200,
        "daily_ingress_budget_bytes": 1024 * 1024 * 1024 * 1024,
        "sign_requests_per_upload_limit": 512,
        "large_export_worker_threshold_bytes": 50 * 1024 * 1024 * 1024,
    }


@pytest.mark.anyio
async def test_get_transfer_capabilities_returns_effective_policy() -> None:
    """Transfer capabilities should expose the resolved policy envelope."""
    service = _build_service()

    response = await service.get_transfer_capabilities(
        workload_class="browser",
        policy_hint="preferred",
    )

    assert response.policy_id == "default"
    assert response.policy_version == "2026-04-03"
    assert response.max_upload_bytes == 500 * 1024 * 1024 * 1024
    assert response.multipart_threshold_bytes == 100 * 1024 * 1024
    assert response.target_upload_part_count == 2000
    assert response.minimum_part_size_bytes == 64 * 1024 * 1024
    assert response.maximum_part_size_bytes == 512 * 1024 * 1024
    assert response.max_concurrency_hint == 4
    assert response.sign_batch_size_hint == 64
    assert response.accelerate_enabled is False
    assert response.checksum_algorithm is None
    assert response.checksum_mode == "none"
    assert response.resumable_ttl_seconds == 7 * 24 * 60 * 60
    assert response.active_multipart_upload_limit == 200
    assert response.daily_ingress_budget_bytes == 1024 * 1024 * 1024 * 1024
    assert response.sign_requests_per_upload_limit == 512
    assert response.large_export_worker_threshold_bytes == (
        50 * 1024 * 1024 * 1024
    )


def test_plan_resources_applies_runtime_feature_flags() -> None:
    """Resource planning should preserve support keys and flag downgrades."""
    settings = _build_settings()
    settings.exports_enabled = False
    settings.file_transfer_enabled = False
    service = _build_service(settings=settings)

    response = service.plan_resources(
        payload=ResourcePlanRequest(
            resources=["exports", "transfers", "downloads", "unknown"]
        )
    )

    assert response.model_dump(mode="json") == {
        "plan": [
            {
                "resource": "exports",
                "supported": False,
                "reason": "exports_disabled",
            },
            {
                "resource": "transfers",
                "supported": False,
                "reason": "file_transfers_disabled",
            },
            {
                "resource": "downloads",
                "supported": False,
                "reason": "file_transfers_disabled",
            },
            {
                "resource": "unknown",
                "supported": False,
                "reason": "unsupported_resource",
            },
        ]
    }


def test_get_release_info_returns_public_metadata() -> None:
    """Release info should come directly from public runtime settings."""
    service = _build_service()

    response = service.get_release_info()

    assert response.model_dump(mode="json") == {
        "name": "nova-test",
        "version": "1.2.3",
        "environment": "test",
    }


@pytest.mark.anyio
async def test_get_metrics_summary_requires_metrics_read_permission() -> None:
    """Metrics summary should enforce the existing permission contract."""
    service = _build_service()

    with pytest.raises(FileTransferError) as exc_info:
        await service.get_metrics_summary(
            principal=Principal(
                subject="caller-1",
                scope_id="scope-1",
                permissions=(),
            )
        )

    error = exc_info.value
    assert error.code == "forbidden"
    assert str(error) == "missing metrics:read permission"


@pytest.mark.anyio
async def test_get_metrics_summary_returns_activity_and_metric_snapshots() -> (
    None
):
    """Metrics summary should expose the current snapshots."""
    metrics = MetricsCollector(namespace="Tests")
    metrics.incr("requests_total")
    metrics.observe_ms("exports_create_ms", 12.345)
    activity_store = MemoryActivityStore()
    principal = Principal(subject="caller-1", scope_id="scope-1")
    await activity_store.record(
        principal=principal,
        event_type="exports_create",
    )
    service = _build_service(metrics=metrics, activity_store=activity_store)

    response = await service.get_metrics_summary(
        principal=principal.model_copy(
            update={"permissions": ("metrics:read",)}
        )
    )

    assert response.model_dump(mode="json") == {
        "counters": {"requests_total": 1},
        "latencies_ms": {"exports_create_ms": 12.345},
        "activity": {
            "events_total": 1,
            "active_users_today": 1,
            "distinct_event_types": 1,
        },
    }
