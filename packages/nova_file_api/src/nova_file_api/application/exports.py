"""Application-layer export request orchestration."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from nova_file_api.activity import ActivityStore
from nova_file_api.exports import ExportService
from nova_file_api.guarded_mutation import run_guarded_mutation
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.models import (
    CreateExportRequest,
    ExportListResponse,
    ExportResource,
    Principal,
)
from nova_file_api.request_metrics import emit_request_metric
from nova_runtime_support.metrics import MetricsCollector


@dataclass(slots=True)
class ExportApplicationService:
    """Own request orchestration for export routes.

    Args:
        metrics: Metrics collector used for timers and request counters.
        export_service: Domain service that owns export lifecycle behavior.
        activity_store: Activity backend used to record caller-visible events.
        idempotency_store: Store used to deduplicate create-export requests.

    Returns:
        ExportApplicationService: Configured application service instance.

    Raises:
        None: Construction does not raise directly.
    """

    metrics: MetricsCollector
    export_service: ExportService
    activity_store: ActivityStore
    idempotency_store: IdempotencyStore

    async def create_export(
        self,
        *,
        payload: CreateExportRequest,
        principal: Principal,
        request_id: str | None,
        idempotency_key: str | None,
    ) -> ExportResource:
        """Create an export below the route boundary.

        Args:
            payload: Request body containing the source key and filename.
            principal: Authorized caller whose scope owns the export.
            request_id: Optional request identifier used for correlation.
            idempotency_key: Optional idempotency key for request replay.

        Returns:
            ExportResource: Public export resource created for the caller.

        Raises:
            Exception: Propagates errors from `run_guarded_mutation`, including
                idempotency-store failures, response persistence failures, and
                errors from `self.export_service.create`.
        """
        request_payload = payload.model_dump(mode="json")

        async def _execute() -> ExportResource:
            with self.metrics.timed("exports_create_ms"):
                export = await self.export_service.create(
                    source_key=payload.source_key,
                    filename=payload.filename,
                    scope_id=principal.scope_id,
                    request_id=request_id,
                )
            return ExportResource.from_record(export)

        async def _on_failure(exc: Exception) -> None:
            await self._record_failure(
                metric_name="exports_create_failure_total",
                route_metric="exports_create",
                log_event="exports_create_request_failed",
                route_path="/v1/exports",
                activity_event_type="exports_create_failure",
                principal=principal,
                exc=exc,
                extra={"idempotency_key": idempotency_key},
            )

        async def _on_success(_: ExportResource) -> None:
            try:
                await self.activity_store.record(
                    principal=principal,
                    event_type="exports_create",
                    details=f"request_id={request_id or 'unknown'}",
                )
            except Exception:
                structlog.get_logger("api").exception(
                    "exports_create_response_finalize_failed",
                    route="/v1/exports",
                    scope_id=principal.scope_id,
                    idempotency_key=idempotency_key,
                )
            self.metrics.incr("exports_create_total")
            emit_request_metric(
                metrics=self.metrics,
                route="exports_create",
                status="ok",
            )

        def _replay_metric() -> None:
            self.metrics.incr("idempotency_replays_total")

        return await run_guarded_mutation(
            route="/v1/exports",
            scope_id=principal.scope_id,
            request_payload=request_payload,
            idempotency_store=self.idempotency_store,
            idempotency_key=idempotency_key,
            response_model=ExportResource,
            replay_metric=_replay_metric,
            execute=_execute,
            on_failure=_on_failure,
            on_success=_on_success,
            store_response_failure_event=(
                "exports_create_idempotency_store_response_failed"
            ),
            store_response_failure_extra={
                "route": "/v1/exports",
                "scope_id": principal.scope_id,
                "idempotency_key": idempotency_key,
            },
            store_response_failure_mode="raise",
        )

    async def get_export(
        self,
        *,
        export_id: str,
        principal: Principal,
    ) -> ExportResource:
        """Get an export below the route boundary.

        Args:
            export_id: Identifier of the caller-owned export resource.
            principal: Authorized caller whose scope owns the export.

        Returns:
            ExportResource: Public export resource matched by export ID.

        Raises:
            Exception: Propagates errors from `self.export_service.get`.
        """
        try:
            export = await self.export_service.get(
                export_id=export_id,
                scope_id=principal.scope_id,
            )
        except Exception as exc:
            await self._record_failure(
                metric_name="exports_get_failure_total",
                route_metric="exports_get",
                log_event="exports_get_request_failed",
                route_path="/v1/exports/{export_id}",
                activity_event_type="exports_get_failure",
                principal=principal,
                exc=exc,
                extra={"export_id": export_id},
            )
            raise

        try:
            self.metrics.incr("exports_get_total")
            emit_request_metric(
                metrics=self.metrics,
                route="exports_get",
                status="ok",
            )
        except Exception:
            structlog.get_logger("api").exception(
                "exports_get_success_side_effects_failed",
                route="/v1/exports/{export_id}",
                scope_id=principal.scope_id,
                export_id=export_id,
            )
        return ExportResource.from_record(export)

    async def list_exports(
        self,
        *,
        scope_id: str,
        limit: int,
    ) -> ExportListResponse:
        """List caller-owned exports below the route boundary.

        Args:
            scope_id: Scope identifier whose exports should be listed.
            limit: Maximum number of export records to return.

        Returns:
            ExportListResponse: Caller-owned exports ordered by recency.

        Raises:
            Exception: Propagates errors from
                `self.export_service.list_for_scope`.
        """
        exports = await self.export_service.list_for_scope(
            scope_id=scope_id,
            limit=limit,
        )
        return ExportListResponse(
            exports=[ExportResource.from_record(export) for export in exports]
        )

    async def cancel_export(
        self,
        *,
        export_id: str,
        principal: Principal,
    ) -> ExportResource:
        """Cancel an export below the route boundary.

        Args:
            export_id: Identifier of the caller-owned export resource.
            principal: Authorized caller whose scope owns the export.

        Returns:
            ExportResource: Public export resource after cancellation.

        Raises:
            Exception: Propagates errors from `self.export_service.cancel`.
        """
        try:
            export = await self.export_service.cancel(
                export_id=export_id,
                scope_id=principal.scope_id,
            )
        except Exception as exc:
            await self._record_failure(
                metric_name="exports_cancel_failure_total",
                route_metric="exports_cancel",
                log_event="exports_cancel_request_failed",
                route_path="/v1/exports/{export_id}/cancel",
                activity_event_type="exports_cancel_failure",
                principal=principal,
                exc=exc,
                extra={"export_id": export_id},
            )
            raise

        try:
            await self.activity_store.record(
                principal=principal,
                event_type="exports_cancel_success",
                details=f"export_id={export.export_id} status={export.status}",
            )
        except Exception:
            structlog.get_logger("api").exception(
                "exports_cancel_activity_record_failed",
                export_id=export.export_id,
                status=export.status,
            )
        try:
            self.metrics.incr("exports_cancel_total")
            emit_request_metric(
                metrics=self.metrics,
                route="exports_cancel",
                status="ok",
            )
        except Exception:
            structlog.get_logger("api").exception(
                "exports_cancel_success_side_effects_failed",
                route="/v1/exports/{export_id}/cancel",
                scope_id=principal.scope_id,
                export_id=export_id,
            )
        return ExportResource.from_record(export)

    async def _record_failure(
        self,
        *,
        metric_name: str,
        route_metric: str,
        log_event: str,
        route_path: str,
        activity_event_type: str,
        principal: Principal,
        exc: Exception,
        extra: dict[str, object] | None = None,
        activity_details: str | None = None,
    ) -> None:
        error_name = type(exc).__name__
        try:
            self.metrics.incr(metric_name)
            emit_request_metric(
                metrics=self.metrics,
                route=route_metric,
                status="error",
            )
        except Exception:
            structlog.get_logger("api").exception(
                "exports_failure_metric_emit_failed",
                route=route_path,
                scope_id=principal.scope_id,
                metric_name=metric_name,
                route_metric=route_metric,
            )

        log_fields: dict[str, object] = {
            "route": route_path,
            "scope_id": principal.scope_id,
            "error": error_name,
            "error_detail": error_name,
        }
        if extra:
            log_fields.update(extra)
        structlog.get_logger("api").exception(log_event, **log_fields)

        try:
            await self.activity_store.record(
                principal=principal,
                event_type=activity_event_type,
                details=activity_details or error_name,
            )
        except Exception:
            structlog.get_logger("api").exception(
                "exports_failure_activity_record_failed",
                route=route_path,
                scope_id=principal.scope_id,
                event_type=activity_event_type,
            )
