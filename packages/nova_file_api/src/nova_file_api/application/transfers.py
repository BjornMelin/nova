"""Application-layer transfer request orchestration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

import structlog
from pydantic import BaseModel

from nova_file_api.activity import ActivityStore
from nova_file_api.guarded_mutation import run_guarded_mutation
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.models import (
    AbortUploadRequest,
    AbortUploadResponse,
    CompleteUploadRequest,
    CompleteUploadResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    PresignDownloadRequest,
    PresignDownloadResponse,
    Principal,
    SignPartsRequest,
    SignPartsResponse,
    UploadIntrospectionRequest,
    UploadIntrospectionResponse,
)
from nova_file_api.request_metrics import emit_request_metric
from nova_file_api.transfer import TransferService
from nova_runtime_support.metrics import MetricsCollector

ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class _TransferRouteSpec:
    route: str
    route_metric: str
    timer_metric: str
    success_metric: str
    failure_metric: str
    request_failed_event: str
    activity_event_type: str
    failure_activity_event_type: str
    activity_record_failed_event: str
    metric_increment_failed_event: str
    metric_emit_failed_event: str


_INITIATE_UPLOAD = _TransferRouteSpec(
    route="/v1/transfers/uploads/initiate",
    route_metric="uploads_initiate",
    timer_metric="uploads_initiate_ms",
    success_metric="uploads_initiate_total",
    failure_metric="uploads_initiate_failure_total",
    request_failed_event="initiate_upload_request_failed",
    activity_event_type="uploads_initiate",
    failure_activity_event_type="uploads_initiate_failure",
    activity_record_failed_event="uploads_initiate_activity_record_failed",
    metric_increment_failed_event="uploads_initiate_metric_increment_failed",
    metric_emit_failed_event="uploads_initiate_metric_emit_failed",
)
_SIGN_PARTS = _TransferRouteSpec(
    route="/v1/transfers/uploads/sign-parts",
    route_metric="uploads_sign_parts",
    timer_metric="uploads_sign_parts_ms",
    success_metric="uploads_sign_parts_total",
    failure_metric="uploads_sign_parts_failure_total",
    request_failed_event="sign_parts_upload_request_failed",
    activity_event_type="uploads_sign_parts",
    failure_activity_event_type="uploads_sign_parts_failure",
    activity_record_failed_event="uploads_sign_parts_activity_record_failed",
    metric_increment_failed_event="uploads_sign_parts_metric_increment_failed",
    metric_emit_failed_event="uploads_sign_parts_metric_emit_failed",
)
_INTROSPECT_UPLOAD = _TransferRouteSpec(
    route="/v1/transfers/uploads/introspect",
    route_metric="uploads_introspect",
    timer_metric="uploads_introspect_ms",
    success_metric="uploads_introspect_total",
    failure_metric="uploads_introspect_failure_total",
    request_failed_event="introspect_upload_request_failed",
    activity_event_type="uploads_introspect",
    failure_activity_event_type="uploads_introspect_failure",
    activity_record_failed_event="uploads_introspect_activity_record_failed",
    metric_increment_failed_event="uploads_introspect_metric_increment_failed",
    metric_emit_failed_event="uploads_introspect_metric_emit_failed",
)
_COMPLETE_UPLOAD = _TransferRouteSpec(
    route="/v1/transfers/uploads/complete",
    route_metric="uploads_complete",
    timer_metric="uploads_complete_ms",
    success_metric="uploads_complete_total",
    failure_metric="uploads_complete_failure_total",
    request_failed_event="complete_upload_request_failed",
    activity_event_type="uploads_complete",
    failure_activity_event_type="uploads_complete_failure",
    activity_record_failed_event="uploads_complete_activity_record_failed",
    metric_increment_failed_event="uploads_complete_metric_increment_failed",
    metric_emit_failed_event="uploads_complete_metric_emit_failed",
)
_ABORT_UPLOAD = _TransferRouteSpec(
    route="/v1/transfers/uploads/abort",
    route_metric="uploads_abort",
    timer_metric="uploads_abort_ms",
    success_metric="uploads_abort_total",
    failure_metric="uploads_abort_failure_total",
    request_failed_event="abort_upload_request_failed",
    activity_event_type="uploads_abort",
    failure_activity_event_type="uploads_abort_failure",
    activity_record_failed_event="uploads_abort_activity_record_failed",
    metric_increment_failed_event="uploads_abort_metric_increment_failed",
    metric_emit_failed_event="uploads_abort_metric_emit_failed",
)
_PRESIGN_DOWNLOAD = _TransferRouteSpec(
    route="/v1/transfers/downloads/presign",
    route_metric="downloads_presign",
    timer_metric="downloads_presign_ms",
    success_metric="downloads_presign_total",
    failure_metric="downloads_presign_failure_total",
    request_failed_event="presign_download_request_failed",
    activity_event_type="downloads_presign",
    failure_activity_event_type="downloads_presign_failure",
    activity_record_failed_event="downloads_presign_activity_record_failed",
    metric_increment_failed_event="downloads_presign_metric_increment_failed",
    metric_emit_failed_event="downloads_presign_metric_emit_failed",
)


@dataclass(slots=True)
class TransferApplicationService:
    """Own request orchestration for transfer routes."""

    metrics: MetricsCollector
    transfer_service: TransferService
    activity_store: ActivityStore
    idempotency_store: IdempotencyStore

    async def initiate_upload(
        self,
        *,
        payload: InitiateUploadRequest,
        principal: Principal,
        idempotency_key: str | None,
    ) -> InitiateUploadResponse:
        """Run the initiate-upload request flow below the route boundary."""
        request_payload = payload.model_dump(mode="json")

        async def _execute() -> InitiateUploadResponse:
            with self.metrics.timed(_INITIATE_UPLOAD.timer_metric):
                return await self.transfer_service.initiate_upload(
                    payload,
                    principal,
                )

        async def _on_failure(exc: Exception) -> None:
            await self._record_failure(
                spec=_INITIATE_UPLOAD,
                principal=principal,
                exc=exc,
            )

        async def _on_success(_: InitiateUploadResponse) -> None:
            await self._record_success(
                spec=_INITIATE_UPLOAD,
                principal=principal,
            )

        def _replay_metric() -> None:
            self._increment_metric_best_effort(
                principal=principal,
                metric_name="idempotency_replays_total",
                route_path=_INITIATE_UPLOAD.route,
                event_name=_INITIATE_UPLOAD.metric_increment_failed_event,
            )

        return await run_guarded_mutation(
            route=_INITIATE_UPLOAD.route,
            scope_id=principal.scope_id,
            request_payload=request_payload,
            idempotency_store=self.idempotency_store,
            idempotency_key=idempotency_key,
            response_model=InitiateUploadResponse,
            replay_metric=_replay_metric,
            execute=_execute,
            on_failure=_on_failure,
            on_success=_on_success,
            store_response_failure_event=(
                "uploads_initiate_idempotency_store_response_failed"
            ),
            store_response_failure_extra={
                "route": _INITIATE_UPLOAD.route,
                "scope_id": principal.scope_id,
            },
            store_response_failure_mode="raise",
        )

    async def sign_parts(
        self,
        *,
        payload: SignPartsRequest,
        principal: Principal,
    ) -> SignPartsResponse:
        """Run the sign-parts request flow below the route boundary."""
        return await self._run_observed_operation(
            spec=_SIGN_PARTS,
            principal=principal,
            operation=lambda: self.transfer_service.sign_parts(
                payload,
                principal,
            ),
        )

    async def introspect_upload(
        self,
        *,
        payload: UploadIntrospectionRequest,
        principal: Principal,
    ) -> UploadIntrospectionResponse:
        """Run upload introspection below the route boundary."""
        return await self._run_observed_operation(
            spec=_INTROSPECT_UPLOAD,
            principal=principal,
            operation=lambda: self.transfer_service.introspect_upload(
                payload,
                principal,
            ),
        )

    async def complete_upload(
        self,
        *,
        payload: CompleteUploadRequest,
        principal: Principal,
    ) -> CompleteUploadResponse:
        """Run the complete-upload request flow below the route boundary."""
        return await self._run_observed_operation(
            spec=_COMPLETE_UPLOAD,
            principal=principal,
            operation=lambda: self.transfer_service.complete_upload(
                payload,
                principal,
            ),
        )

    async def abort_upload(
        self,
        *,
        payload: AbortUploadRequest,
        principal: Principal,
    ) -> AbortUploadResponse:
        """Run the abort-upload request flow below the route boundary."""
        return await self._run_observed_operation(
            spec=_ABORT_UPLOAD,
            principal=principal,
            operation=lambda: self.transfer_service.abort_upload(
                payload,
                principal,
            ),
        )

    async def presign_download(
        self,
        *,
        payload: PresignDownloadRequest,
        principal: Principal,
    ) -> PresignDownloadResponse:
        """Run the download-presign request flow below the route boundary."""
        return await self._run_observed_operation(
            spec=_PRESIGN_DOWNLOAD,
            principal=principal,
            operation=lambda: self.transfer_service.presign_download(
                payload,
                principal,
            ),
        )

    async def _run_observed_operation(
        self,
        *,
        spec: _TransferRouteSpec,
        principal: Principal,
        operation: Callable[[], Awaitable[ResponseModelT]],
    ) -> ResponseModelT:
        try:
            with self.metrics.timed(spec.timer_metric):
                response = await operation()
        except Exception as exc:
            await self._record_failure(
                spec=spec,
                principal=principal,
                exc=exc,
            )
            raise

        await self._record_success(
            spec=spec,
            principal=principal,
        )
        return response

    async def _record_failure(
        self,
        *,
        spec: _TransferRouteSpec,
        principal: Principal,
        exc: Exception,
    ) -> None:
        self._emit_request_metric_best_effort(
            principal=principal,
            route_metric=spec.route_metric,
            route_path=spec.route,
            event_name="transfer_failure_metric_emit_failed",
            status="error",
            counter_metric=spec.failure_metric,
        )
        structlog.get_logger("api").exception(
            spec.request_failed_event,
            route=spec.route,
            scope_id=principal.scope_id,
            error=type(exc).__name__,
            error_code="transfer_failure",
        )
        try:
            await self.activity_store.record(
                principal=principal,
                event_type=spec.failure_activity_event_type,
                details=type(exc).__name__,
            )
        except Exception:
            structlog.get_logger("api").exception(
                "transfer_failure_activity_record_failed",
                route=spec.route,
                scope_id=principal.scope_id,
                event_type=spec.failure_activity_event_type,
            )

    async def _record_success(
        self,
        *,
        spec: _TransferRouteSpec,
        principal: Principal,
    ) -> None:
        self._increment_metric_best_effort(
            principal=principal,
            metric_name=spec.success_metric,
            route_path=spec.route,
            event_name=spec.metric_increment_failed_event,
        )
        try:
            await self.activity_store.record(
                principal=principal,
                event_type=spec.activity_event_type,
            )
        except Exception:
            structlog.get_logger("api").exception(
                spec.activity_record_failed_event,
                route=spec.route,
                scope_id=principal.scope_id,
            )
        self._emit_request_metric_best_effort(
            principal=principal,
            route_metric=spec.route_metric,
            route_path=spec.route,
            event_name=spec.metric_emit_failed_event,
            status="ok",
        )

    def _emit_request_metric_best_effort(
        self,
        *,
        principal: Principal,
        route_metric: str,
        route_path: str,
        event_name: str,
        status: str,
        counter_metric: str | None = None,
    ) -> None:
        try:
            if counter_metric is not None:
                self.metrics.incr(counter_metric)
            emit_request_metric(
                metrics=self.metrics,
                route=route_metric,
                status=status,
            )
        except Exception:
            structlog.get_logger("api").exception(
                event_name,
                route=route_path,
                scope_id=principal.scope_id,
                status=status,
                counter_metric=counter_metric,
            )

    def _increment_metric_best_effort(
        self,
        *,
        principal: Principal,
        metric_name: str,
        route_path: str,
        event_name: str,
    ) -> None:
        try:
            self.metrics.incr(metric_name)
        except Exception:
            structlog.get_logger("api").exception(
                event_name,
                route=route_path,
                scope_id=principal.scope_id,
                metric_name=metric_name,
            )
