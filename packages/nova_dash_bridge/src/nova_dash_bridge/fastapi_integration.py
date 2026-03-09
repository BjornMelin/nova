"""Optional FastAPI adapter for canonical file transfer endpoints."""
# mypy: disable-error-code="untyped-decorator"

from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any

import anyio
from anyio.abc import CapacityLimiter

from nova_dash_bridge.config import (
    AuthPolicy,
    FileTransferEnvConfig,
    UploadPolicy,
)
from nova_dash_bridge.errors import validation_error
from nova_dash_bridge.http_adapter_core import (
    coerce_error_response,
    execute_operation,
)
from nova_dash_bridge.s3_client import SupportsCreateS3Client
from nova_dash_bridge.service import FileTransferService

LOGGER = logging.getLogger(__name__)
_CANONICAL_TRANSFERS_PREFIX = "/v1/transfers"

if TYPE_CHECKING:
    from fastapi import Request
else:  # pragma: no cover
    try:
        from fastapi import Request
    except ModuleNotFoundError:
        Request = Any  # type: ignore[misc,assignment]


def _fastapi_imports() -> tuple[type[Any], type[Any], type[Any]]:
    """Load FastAPI symbols only when the optional dependency is installed."""
    try:
        from fastapi import APIRouter, FastAPI
        from fastapi.responses import JSONResponse
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "FastAPI integration requires optional dependency group `fastapi`"
        ) from exc
    return APIRouter, FastAPI, JSONResponse


def _request_id(request: Request) -> str | None:
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    value = headers.get("X-Request-Id")
    return value if isinstance(value, str) else None


def create_fastapi_router(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy | None = None,
    s3_client_factory: SupportsCreateS3Client | None = None,
) -> Any:
    """Create an APIRouter for the canonical bridge transfer endpoints."""
    apirouter, _, json_response = _fastapi_imports()
    router = apirouter()
    service = FileTransferService(
        env_config=env_config,
        upload_policy=upload_policy,
        auth_policy=auth_policy,
        s3_client_factory=s3_client_factory,
    )
    blocking_io_limiter: CapacityLimiter | None = None

    async def run_operation(
        *,
        request: Request,
        operation_name: str,
    ) -> Any:
        nonlocal blocking_io_limiter
        if blocking_io_limiter is None:
            blocking_io_limiter = anyio.CapacityLimiter(
                env_config.thread_tokens
            )
        try:
            try:
                raw_payload = await request.json()
            except Exception as exc:
                raise validation_error(
                    "request body must be valid JSON"
                ) from exc
            return await anyio.to_thread.run_sync(
                partial(
                    execute_operation,
                    service=service,
                    operation_name=operation_name,
                    raw_payload=raw_payload,
                ),
                limiter=blocking_io_limiter,
            )
        except Exception as exc:  # noqa: BLE001
            status_code, content = coerce_error_response(
                exc=exc,
                request_id=_request_id(request),
                logger=LOGGER,
                log_event="fastapi_file_transfer_request_failed",
            )
            return json_response(status_code=status_code, content=content)

    @router.post("/uploads/initiate")
    async def initiate_upload(request: Request) -> Any:
        return await run_operation(
            request=request,
            operation_name="initiate_upload",
        )

    @router.post("/uploads/sign-parts")
    async def sign_parts(request: Request) -> Any:
        return await run_operation(request=request, operation_name="sign_parts")

    @router.post("/uploads/complete")
    async def complete_upload(request: Request) -> Any:
        return await run_operation(
            request=request,
            operation_name="complete_upload",
        )

    @router.post("/uploads/abort")
    async def abort_upload(request: Request) -> Any:
        return await run_operation(
            request=request,
            operation_name="abort_upload",
        )

    @router.post("/downloads/presign")
    async def presign_download(request: Request) -> Any:
        return await run_operation(
            request=request,
            operation_name="presign_download",
        )

    return router


def create_fastapi_app(
    *,
    env_config: FileTransferEnvConfig,
    upload_policy: UploadPolicy,
    auth_policy: AuthPolicy | None = None,
    s3_client_factory: SupportsCreateS3Client | None = None,
) -> Any:
    """Create a minimal FastAPI app with canonical transfer routes."""
    _, fastapi, _ = _fastapi_imports()
    app = fastapi()
    app.include_router(
        create_fastapi_router(
            env_config=env_config,
            upload_policy=upload_policy,
            auth_policy=auth_policy,
            s3_client_factory=s3_client_factory,
        ),
        prefix=_CANONICAL_TRANSFERS_PREFIX,
    )
    return app
