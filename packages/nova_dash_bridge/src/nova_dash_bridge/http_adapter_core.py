"""Shared HTTP adapter core for FastAPI and Flask bridge integrations."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from nova_file_api.errors import FileTransferError as CoreFileTransferError
from nova_runtime_support import canonical_error_content
from pydantic import ValidationError

from nova_dash_bridge.errors import FileTransferError, validation_error
from nova_dash_bridge.models import (
    AbortUploadRequest,
    CompleteUploadRequest,
    InitiateUploadRequest,
    PresignDownloadRequest,
    SignPartsRequest,
)
from nova_dash_bridge.service import (
    FileTransferService,
    coerce_file_transfer_error,
)


@dataclass(frozen=True, slots=True)
class OperationDefinition:
    """Bridge operation dispatch metadata."""

    request_model: type[Any]
    service_method_name: str


_OPERATION_DEFINITIONS: dict[str, OperationDefinition] = {
    "initiate_upload": OperationDefinition(
        request_model=InitiateUploadRequest,
        service_method_name="initiate_upload",
    ),
    "sign_parts": OperationDefinition(
        request_model=SignPartsRequest,
        service_method_name="sign_parts",
    ),
    "complete_upload": OperationDefinition(
        request_model=CompleteUploadRequest,
        service_method_name="complete_upload",
    ),
    "abort_upload": OperationDefinition(
        request_model=AbortUploadRequest,
        service_method_name="abort_upload",
    ),
    "presign_download": OperationDefinition(
        request_model=PresignDownloadRequest,
        service_method_name="presign_download",
    ),
}


def execute_operation(
    *,
    service: FileTransferService,
    operation_name: str,
    raw_payload: Any,
) -> Any:
    """Validate input payload and dispatch one bridge transfer operation."""
    definition = _OPERATION_DEFINITIONS[operation_name]
    payload = parse_payload(
        raw_payload=raw_payload,
        model=definition.request_model,
    )
    method = cast(
        Callable[[Any], Any],
        getattr(service, definition.service_method_name),
    )
    return method(payload)


def parse_payload(*, raw_payload: Any, model: type[Any]) -> Any:
    """Validate request JSON into one bridge request model."""
    if raw_payload is None:
        raise validation_error("request body must not be null")
    try:
        return model.model_validate(raw_payload)
    except ValidationError as exc:
        raise validation_error(
            "invalid request payload",
            details={"errors": exc.errors()},
        ) from exc
    except Exception as exc:
        raise validation_error("request body must be valid JSON") from exc


def coerce_error_response(
    *,
    exc: Exception,
    request_id: str | None,
    logger: logging.Logger,
    log_event: str,
) -> tuple[int, dict[str, Any]]:
    """Coerce any bridge exception into a canonical error response payload."""
    if not isinstance(exc, (FileTransferError, CoreFileTransferError)):
        logger.exception(log_event, extra={"error_type": type(exc).__name__})
    err = coerce_file_transfer_error(exc)
    return int(err.status_code), canonical_error_content(
        code=err.code,
        message=err.message,
        details=err.details,
        request_id=request_id,
    )
