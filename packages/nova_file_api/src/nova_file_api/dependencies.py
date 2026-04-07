"""FastAPI dependency helpers rooted on the typed API runtime container."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from nova_file_api import runtime as runtime_module
from nova_file_api.activity import ActivityStore
from nova_file_api.application import (
    ExportApplicationService,
    TransferApplicationService,
)
from nova_file_api.auth import Authenticator
from nova_file_api.cache import TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.export_runtime import ExportRepository
from nova_file_api.exports import ExportService
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.models import Principal
from nova_file_api.runtime import ApiRuntime
from nova_file_api.transfer import TransferService
from nova_runtime_support.metrics import MetricsCollector

_APPLICATION_STATE_NOT_INITIALIZED = "application state is not initialized"
build_activity_store = runtime_module.build_activity_store
build_export_publisher = runtime_module.build_export_publisher
_BEARER_AUTH = HTTPBearer(
    auto_error=False,
    scheme_name="bearerAuth",
    bearerFormat="JWT",
    description=(
        "Bearer JWT for public Nova file API requests. Scope and tenancy "
        "are derived from verified claims."
    ),
)


def get_runtime(request: Request) -> ApiRuntime:
    """Return the typed runtime container from application state."""
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise TypeError(_APPLICATION_STATE_NOT_INITIALIZED)
    return cast(ApiRuntime, runtime)


def get_settings(
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> Settings:
    """Return application settings from the typed runtime container."""
    return runtime.settings


def get_metrics(
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> MetricsCollector:
    """Return the metrics collector from the typed runtime container."""
    return runtime.metrics


def get_two_tier_cache(
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> TwoTierCache:
    """Return the two-tier cache from the typed runtime container."""
    return runtime.cache


def get_transfer_service(
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> TransferService:
    """Return the transfer service from the typed runtime container."""
    return runtime.transfer_service


def get_export_repository(
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> ExportRepository:
    """Return the export repository from the typed runtime container."""
    return runtime.export_repository


def get_export_service(
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> ExportService:
    """Return the export service from the typed runtime container."""
    return runtime.export_service


def get_activity_store(
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> ActivityStore:
    """Return the activity store from the typed runtime container."""
    return runtime.activity_store


def get_idempotency_store(
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> IdempotencyStore:
    """Return the idempotency store from the typed runtime container."""
    return runtime.idempotency_store


def get_authenticator(
    runtime: Annotated[ApiRuntime, Depends(get_runtime)],
) -> Authenticator:
    """Return the authenticator from the typed runtime container."""
    return runtime.authenticator


async def authenticate_principal(
    *,
    authenticator: Authenticator,
    credentials: HTTPAuthorizationCredentials | None,
) -> Principal:
    """Authenticate the current caller for a request."""
    return await authenticator.authenticate(
        token=(credentials.credentials if credentials is not None else None),
    )


async def get_principal(
    authenticator: Annotated[Authenticator, Depends(get_authenticator)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(_BEARER_AUTH),
    ],
) -> Principal:
    """Authenticate a bearer-authenticated public API request."""
    return await authenticate_principal(
        authenticator=authenticator,
        credentials=credentials,
    )


def get_transfer_application_service(
    metrics: Annotated[MetricsCollector, Depends(get_metrics)],
    transfer_service: Annotated[TransferService, Depends(get_transfer_service)],
    activity_store: Annotated[ActivityStore, Depends(get_activity_store)],
    idempotency_store: Annotated[
        IdempotencyStore, Depends(get_idempotency_store)
    ],
) -> TransferApplicationService:
    """Build the per-request transfer application coordinator.

    Args:
        metrics: Metrics collector used for request timers and counters.
        transfer_service: Domain transfer service bound to the runtime.
        activity_store: Activity backend used to record caller-visible events.
        idempotency_store: Store used to deduplicate create-upload requests.

    Returns:
        TransferApplicationService: Per-request transfer application service.

    Raises:
        Exception: Propagates dependency-resolution or construction failures.
    """
    return TransferApplicationService(
        metrics=metrics,
        transfer_service=transfer_service,
        activity_store=activity_store,
        idempotency_store=idempotency_store,
    )


def get_export_application_service(
    metrics: Annotated[MetricsCollector, Depends(get_metrics)],
    export_service: Annotated[ExportService, Depends(get_export_service)],
    activity_store: Annotated[ActivityStore, Depends(get_activity_store)],
    idempotency_store: Annotated[
        IdempotencyStore, Depends(get_idempotency_store)
    ],
) -> ExportApplicationService:
    """Build the per-request export application coordinator.

    Args:
        metrics: Metrics collector used for request timers and counters.
        export_service: Domain export service bound to the runtime.
        activity_store: Activity backend used to record caller-visible events.
        idempotency_store: Store used to deduplicate create-export requests.

    Returns:
        ExportApplicationService: Per-request export application service.

    Raises:
        Exception: Propagates dependency-resolution or construction failures.
    """
    return ExportApplicationService(
        metrics=metrics,
        export_service=export_service,
        activity_store=activity_store,
        idempotency_store=idempotency_store,
    )


RuntimeDep = Annotated[ApiRuntime, Depends(get_runtime)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
MetricsDep = Annotated[MetricsCollector, Depends(get_metrics)]
TwoTierCacheDep = Annotated[TwoTierCache, Depends(get_two_tier_cache)]
TransferServiceDep = Annotated[TransferService, Depends(get_transfer_service)]
TransferApplicationServiceDep = Annotated[
    TransferApplicationService,
    Depends(get_transfer_application_service),
]
ExportRepositoryDep = Annotated[
    ExportRepository, Depends(get_export_repository)
]
ExportServiceDep = Annotated[ExportService, Depends(get_export_service)]
ExportApplicationServiceDep = Annotated[
    ExportApplicationService,
    Depends(get_export_application_service),
]
ActivityStoreDep = Annotated[ActivityStore, Depends(get_activity_store)]
IdempotencyStoreDep = Annotated[
    IdempotencyStore,
    Depends(get_idempotency_store),
]
AuthenticatorDep = Annotated[Authenticator, Depends(get_authenticator)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
