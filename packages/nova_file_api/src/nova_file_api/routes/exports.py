"""Export-domain routes for the canonical file API."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from nova_file_api.dependencies import (
    ExportApplicationServiceDep,
    PrincipalDep,
    SettingsDep,
)
from nova_file_api.errors import forbidden
from nova_file_api.models import (
    CreateExportRequest,
    ErrorEnvelope,
    ExportListResponse,
    ExportResource,
)
from nova_file_api.operation_ids import (
    CANCEL_EXPORT_OPERATION_ID,
    CREATE_EXPORT_OPERATION_ID,
    GET_EXPORT_OPERATION_ID,
    LIST_EXPORTS_OPERATION_ID,
)
from nova_file_api.routes.common import (
    COMMON_ERROR_RESPONSES,
    EXPORT_MUTATION_UNAVAILABLE_RESPONSE,
    IDEMPOTENCY_CONFLICT_RESPONSE,
    ExportIdPath,
    ExportsLimitQuery,
    IdempotencyKeyHeader,
    validated_idempotency_key,
)
from nova_runtime_support.http import request_id_from_request

exports_router = APIRouter(
    prefix="/v1",
    tags=["exports"],
    responses=COMMON_ERROR_RESPONSES,
)


@exports_router.post(
    "/exports",
    operation_id=CREATE_EXPORT_OPERATION_ID,
    response_model=ExportResource,
    status_code=status.HTTP_201_CREATED,
    summary="Create an export workflow",
    description=(
        "Create a caller-owned export resource that copies a source object "
        "into a download-oriented export output."
    ),
    response_description="Created export workflow resource.",
    responses=(
        IDEMPOTENCY_CONFLICT_RESPONSE | EXPORT_MUTATION_UNAVAILABLE_RESPONSE
    ),
)
async def create_export(
    payload: CreateExportRequest,
    request: Request,
    settings: SettingsDep,
    export_application_service: ExportApplicationServiceDep,
    principal: PrincipalDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ExportResource:
    """Create an explicit export workflow resource."""
    if not settings.exports_enabled:
        raise forbidden("exports API is disabled")

    key = validated_idempotency_key(
        settings=settings,
        idempotency_key=idempotency_key,
    )
    return await export_application_service.create_export(
        payload=payload,
        principal=principal,
        request_id=request_id_from_request(request=request),
        idempotency_key=key,
    )


@exports_router.get(
    "/exports/{export_id}",
    operation_id=GET_EXPORT_OPERATION_ID,
    response_model=ExportResource,
    summary="Get an export workflow",
    description=(
        "Return the current state of a caller-owned export workflow resource."
    ),
    response_description="Current export workflow resource.",
    responses={
        404: {
            "model": ErrorEnvelope,
            "description": "Not Found - Export resource was not found.",
        }
    },
)
async def get_export(
    export_id: ExportIdPath,
    export_application_service: ExportApplicationServiceDep,
    principal: PrincipalDep,
) -> ExportResource:
    """Return the caller-owned export resource."""
    return await export_application_service.get_export(
        export_id=export_id,
        principal=principal,
    )


@exports_router.get(
    "/exports",
    operation_id=LIST_EXPORTS_OPERATION_ID,
    response_model=ExportListResponse,
    summary="List export workflows",
    description=(
        "List caller-owned export workflow resources with the most recent "
        "exports first."
    ),
    response_description="Page of caller-owned export workflow resources.",
)
async def list_exports(
    export_application_service: ExportApplicationServiceDep,
    principal: PrincipalDep,
    limit: ExportsLimitQuery = 50,
) -> ExportListResponse:
    """List caller-owned exports with most recent first.

    This endpoint is intentionally eventual because it is backed by a scoped
    DynamoDB global secondary index.
    """
    return await export_application_service.list_exports(
        scope_id=principal.scope_id,
        limit=limit,
    )


@exports_router.post(
    "/exports/{export_id}/cancel",
    operation_id=CANCEL_EXPORT_OPERATION_ID,
    response_model=ExportResource,
    summary="Cancel an export workflow",
    description=(
        "Persist cancel intent for a caller-owned export that has not yet "
        "reached a terminal state."
    ),
    response_description=(
        "Updated export workflow resource after cancel intent."
    ),
    responses={
        404: {
            "model": ErrorEnvelope,
            "description": "Not Found - Export resource was not found.",
        }
    },
)
async def cancel_export(
    export_id: ExportIdPath,
    export_application_service: ExportApplicationServiceDep,
    principal: PrincipalDep,
) -> ExportResource:
    """Cancel a caller-owned non-terminal export."""
    return await export_application_service.cancel_export(
        export_id=export_id,
        principal=principal,
    )
