"""Application-layer platform and ops request orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from nova_file_api.activity import ActivityStore
from nova_file_api.auth import Authenticator
from nova_file_api.config import Settings
from nova_file_api.errors import forbidden
from nova_file_api.exports import ExportService
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.models import (
    CapabilitiesResponse,
    CapabilityDescriptor,
    MetricsSummaryResponse,
    Principal,
    ReadinessChecks,
    ReadinessResponse,
    ReleaseInfoResponse,
    ResourcePlanItem,
    ResourcePlanRequest,
    ResourcePlanResponse,
    TransferCapabilitiesResponse,
)
from nova_file_api.request_metrics import emit_request_metric
from nova_file_api.transfer import TransferService
from nova_file_api.transfer_policy import TransferPolicy
from nova_runtime_support.metrics import MetricsCollector

_READINESS_ROUTE = "/v1/health/ready"
_SUPPORTED_RESOURCE_KEYS = frozenset(
    {"exports", "transfers", "downloads", "uploads"}
)


@dataclass(slots=True)
class PlatformApplicationService:
    """Own request orchestration for platform and ops routes."""

    settings: Settings
    metrics: MetricsCollector
    transfer_service: TransferService
    activity_store: ActivityStore

    async def get_capabilities(self) -> CapabilitiesResponse:
        """Expose runtime capability declarations."""
        policy = await self.transfer_service.resolve_policy(scope_id=None)
        return CapabilitiesResponse(
            capabilities=[
                CapabilityDescriptor(
                    key="exports",
                    enabled=self.settings.exports_enabled,
                ),
                CapabilityDescriptor(
                    key="exports.status.poll",
                    enabled=self.settings.exports_enabled,
                ),
                CapabilityDescriptor(
                    key="transfers",
                    enabled=self.settings.file_transfer_enabled,
                ),
                CapabilityDescriptor(
                    key="transfers.policy",
                    enabled=self.settings.file_transfer_enabled,
                    details=_transfer_policy_details(policy),
                ),
            ]
        )

    async def get_transfer_capabilities(
        self,
        *,
        workload_class: str | None,
        policy_hint: str | None,
    ) -> TransferCapabilitiesResponse:
        """Expose the effective transfer policy envelope."""
        policy = await self.transfer_service.resolve_policy(
            scope_id=None,
            workload_class=workload_class,
            policy_hint=policy_hint,
        )
        return TransferCapabilitiesResponse(
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            max_upload_bytes=policy.max_upload_bytes,
            multipart_threshold_bytes=policy.multipart_threshold_bytes,
            target_upload_part_count=policy.target_upload_part_count,
            minimum_part_size_bytes=policy.minimum_part_size_bytes,
            maximum_part_size_bytes=policy.maximum_part_size_bytes,
            max_concurrency_hint=policy.max_concurrency_hint,
            sign_batch_size_hint=policy.sign_batch_size_hint,
            accelerate_enabled=policy.accelerate_enabled,
            checksum_algorithm=policy.checksum_algorithm,
            checksum_mode=policy.checksum_mode,
            resumable_ttl_seconds=policy.resumable_ttl_seconds,
            active_multipart_upload_limit=policy.active_multipart_upload_limit,
            daily_ingress_budget_bytes=policy.daily_ingress_budget_bytes,
            sign_requests_per_upload_limit=policy.sign_requests_per_upload_limit,
            large_export_worker_threshold_bytes=(
                policy.large_export_worker_threshold_bytes
            ),
        )

    def plan_resources(
        self,
        *,
        payload: ResourcePlanRequest,
    ) -> ResourcePlanResponse:
        """Report supportability for requested resource keys."""
        plan = [
            ResourcePlanItem(
                resource=resource,
                supported=resource in _SUPPORTED_RESOURCE_KEYS,
                reason=(
                    None
                    if resource in _SUPPORTED_RESOURCE_KEYS
                    else "unsupported_resource"
                ),
            )
            for resource in payload.resources
        ]
        if not self.settings.exports_enabled:
            plan = [
                item.model_copy(
                    update={
                        "supported": False,
                        "reason": "exports_disabled",
                    }
                )
                if item.resource == "exports"
                else item
                for item in plan
            ]
        if not self.settings.file_transfer_enabled:
            plan = [
                item.model_copy(
                    update={
                        "supported": False,
                        "reason": "file_transfers_disabled",
                    }
                )
                if item.resource in {"transfers", "downloads", "uploads"}
                else item
                for item in plan
            ]
        return ResourcePlanResponse(plan=plan)

    def get_release_info(self) -> ReleaseInfoResponse:
        """Return public release metadata for browser and deploy canaries."""
        return ReleaseInfoResponse(
            name=self.settings.app_name,
            version=self.settings.app_version,
            environment=self.settings.environment,
        )

    async def get_metrics_summary(
        self,
        *,
        principal: Principal,
    ) -> MetricsSummaryResponse:
        """Return low-cardinality metrics and activity rollups."""
        if "metrics:read" not in principal.permissions:
            raise forbidden("missing metrics:read permission")

        activity_summary = await self.activity_store.summary()
        emit_request_metric(
            metrics=self.metrics,
            route="metrics_summary",
            status="ok",
        )
        return MetricsSummaryResponse(
            counters=self.metrics.counters_snapshot(),
            latencies_ms=self.metrics.latency_snapshot(),
            activity=activity_summary,
        )


@dataclass(slots=True)
class ReadinessService:
    """Own readiness policy and dependency checks below the route boundary."""

    settings: Settings
    idempotency_store: IdempotencyStore
    export_service: ExportService
    transfer_service: TransferService
    activity_store: ActivityStore
    authenticator: Authenticator
    logger: Any = field(default_factory=lambda: structlog.get_logger("api"))

    async def get_readiness(self) -> ReadinessResponse:
        """Return readiness checks for traffic-critical dependencies."""
        checks = await self._collect_checks()
        required_checks: tuple[str, ...] = (
            "auth_dependency",
            "export_runtime",
            "transfer_runtime",
        )
        if self.settings.idempotency_enabled:
            required_checks = (*required_checks, "idempotency_store")
        is_ready = all(getattr(checks, name) for name in required_checks)
        return ReadinessResponse(ok=is_ready, checks=checks)

    async def _collect_checks(self) -> ReadinessChecks:
        (
            idempotency_store_ready,
            export_runtime_ready,
            activity_store_ready,
            transfer_runtime_ready,
            auth_dependency_ready,
        ) = await asyncio.gather(
            self._probe_bool(
                healthcheck=self.idempotency_store.healthcheck,
                failure_event=(
                    "v1_health_ready_idempotency_store_healthcheck_failed"
                ),
            ),
            self._probe_export_runtime(),
            self._probe_bool(
                healthcheck=self.activity_store.healthcheck,
                failure_event=(
                    "v1_health_ready_activity_store_healthcheck_failed"
                ),
            ),
            self._probe_bool(
                healthcheck=self.transfer_service.healthcheck,
                failure_event=(
                    "v1_health_ready_transfer_runtime_healthcheck_failed"
                ),
            ),
            self._probe_bool(
                healthcheck=self.authenticator.healthcheck,
                failure_event=(
                    "v1_health_ready_auth_dependency_healthcheck_failed"
                ),
            ),
        )
        return ReadinessChecks(
            idempotency_store=idempotency_store_ready,
            export_runtime=export_runtime_ready,
            activity_store=activity_store_ready,
            transfer_runtime=transfer_runtime_ready,
            auth_dependency=auth_dependency_ready,
        )

    async def _probe_export_runtime(self) -> bool:
        if not self.settings.exports_enabled:
            return True
        publisher_ready, repository_ready = await asyncio.gather(
            self._probe_bool(
                healthcheck=self.export_service.publisher.healthcheck,
                failure_event="v1_health_ready_export_queue_healthcheck_failed",
            ),
            self._probe_bool(
                healthcheck=self.export_service.repository.healthcheck,
                failure_event=(
                    "v1_health_ready_export_repository_healthcheck_failed"
                ),
            ),
        )
        return publisher_ready and repository_ready

    async def _probe_bool(
        self,
        *,
        healthcheck: Callable[[], Awaitable[bool]],
        failure_event: str,
    ) -> bool:
        try:
            return await healthcheck()
        except Exception:
            self.logger.exception(
                failure_event,
                route=_READINESS_ROUTE,
            )
            return False


def _transfer_policy_details(
    policy: TransferPolicy,
) -> dict[str, int | str | bool | None]:
    """Return the public capability details for one resolved transfer policy."""
    return {
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "max_concurrency_hint": policy.max_concurrency_hint,
        "sign_batch_size_hint": policy.sign_batch_size_hint,
        "target_upload_part_count": policy.target_upload_part_count,
        "minimum_part_size_bytes": policy.minimum_part_size_bytes,
        "maximum_part_size_bytes": policy.maximum_part_size_bytes,
        "accelerate_enabled": policy.accelerate_enabled,
        "checksum_algorithm": policy.checksum_algorithm,
        "checksum_mode": policy.checksum_mode,
        "resumable_ttl_seconds": policy.resumable_ttl_seconds,
        "active_multipart_upload_limit": policy.active_multipart_upload_limit,
        "daily_ingress_budget_bytes": policy.daily_ingress_budget_bytes,
        "sign_requests_per_upload_limit": policy.sign_requests_per_upload_limit,
        "large_export_worker_threshold_bytes": (
            policy.large_export_worker_threshold_bytes
        ),
    }
