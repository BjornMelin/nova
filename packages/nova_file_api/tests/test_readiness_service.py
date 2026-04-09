"""Unit tests for readiness orchestration below the route boundary."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.application.platform import ReadinessService
from nova_file_api.auth import Authenticator
from nova_file_api.cache import TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.export_runtime import ExportPublisher, ExportRepository
from nova_file_api.exports import ExportService
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.transfer import TransferService
from nova_runtime_support.metrics import MetricsCollector

from .support.app import build_cache_stack
from .support.doubles import StubAuthenticator, StubTransferService


class _ReadyIdempotencyStore:
    enabled = True

    async def healthcheck(self) -> bool:
        return True


class _FailingIdempotencyStore(_ReadyIdempotencyStore):
    async def healthcheck(self) -> bool:
        return False


class _FailingActivityStore(MemoryActivityStore):
    async def healthcheck(self) -> bool:
        return False


class _FailingTransferService(StubTransferService):
    async def healthcheck(self) -> bool:
        return False


class _ExplodingAuthenticator(StubAuthenticator):
    async def healthcheck(self) -> bool:
        raise RuntimeError("jwks endpoint unavailable")


class _UnreadyAuthenticator(StubAuthenticator):
    async def healthcheck(self) -> bool:
        return False


class _GateProbe:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def healthcheck(self) -> bool:
        self.started.set()
        await self.release.wait()
        return True


class _GateTransferService(StubTransferService):
    def __init__(self, probe: _GateProbe) -> None:
        self._probe = probe

    async def healthcheck(self) -> bool:
        return await self._probe.healthcheck()


class _GateAuthenticator(StubAuthenticator):
    def __init__(self, probe: _GateProbe) -> None:
        self._probe = probe

    async def healthcheck(self) -> bool:
        return await self._probe.healthcheck()


class _GateIdempotencyStore:
    enabled = True

    def __init__(self, probe: _GateProbe) -> None:
        self._probe = probe

    async def healthcheck(self) -> bool:
        return await self._probe.healthcheck()


class _GateActivityStore(MemoryActivityStore):
    def __init__(self, probe: _GateProbe) -> None:
        super().__init__()
        self._probe = probe

    async def healthcheck(self) -> bool:
        return await self._probe.healthcheck()


class _GatePublisher:
    def __init__(self, probe: _GateProbe) -> None:
        self._probe = probe

    async def healthcheck(self) -> bool:
        return await self._probe.healthcheck()


class _GateRepository:
    def __init__(self, probe: _GateProbe) -> None:
        self._probe = probe

    async def healthcheck(self) -> bool:
        return await self._probe.healthcheck()


def _build_settings() -> Settings:
    settings = Settings.model_validate(
        {
            "IDEMPOTENCY_DYNAMODB_TABLE": "test-idempotency",
            "OIDC_ISSUER": "https://issuer.example.com/",
            "OIDC_AUDIENCE": "api://nova",
            "OIDC_JWKS_URL": "https://issuer.example.com/.well-known/jwks.json",
        }
    )
    settings.file_transfer_enabled = True
    settings.exports_enabled = True
    settings.idempotency_enabled = True
    return settings


def _build_export_service(
    *,
    metrics: MetricsCollector | None = None,
) -> ExportService:
    resolved_metrics = (
        MetricsCollector(namespace="Tests") if metrics is None else metrics
    )
    return ExportService(
        repository=cast(ExportRepository, _ReadyExportRepository()),
        publisher=cast(ExportPublisher, _ReadyExportPublisher()),
        metrics=resolved_metrics,
    )


def _build_authenticator(
    *,
    settings: Settings | None = None,
    cache: TwoTierCache | None = None,
) -> Authenticator:
    return Authenticator(
        settings=_build_settings() if settings is None else settings,
        cache=build_cache_stack() if cache is None else cache,
    )


class _ReadyExportPublisher:
    async def healthcheck(self) -> bool:
        return True


class _ReadyExportRepository:
    async def healthcheck(self) -> bool:
        return True


def _build_service(
    *,
    settings: Settings | None = None,
    idempotency_store: Any | None = None,
    export_service: ExportService | None = None,
    transfer_service: Any | None = None,
    activity_store: MemoryActivityStore | None = None,
    authenticator: Any | None = None,
) -> ReadinessService:
    resolved_settings = _build_settings() if settings is None else settings
    resolved_metrics = MetricsCollector(namespace="Tests")
    return ReadinessService(
        settings=resolved_settings,
        idempotency_store=cast(
            IdempotencyStore,
            _ReadyIdempotencyStore()
            if idempotency_store is None
            else idempotency_store,
        ),
        export_service=(
            _build_export_service(metrics=resolved_metrics)
            if export_service is None
            else export_service
        ),
        transfer_service=cast(
            TransferService,
            StubTransferService()
            if transfer_service is None
            else transfer_service,
        ),
        activity_store=(
            MemoryActivityStore() if activity_store is None else activity_store
        ),
        authenticator=cast(
            Authenticator,
            _build_authenticator(settings=resolved_settings)
            if authenticator is None
            else authenticator,
        ),
    )


@pytest.mark.anyio
async def test_get_readiness_returns_expected_checks_when_ready() -> None:
    """Readiness should stay true when required dependencies are healthy."""
    service = _build_service(authenticator=StubAuthenticator())

    response = await service.get_readiness()

    assert response.model_dump(mode="json") == {
        "ok": True,
        "checks": {
            "idempotency_store": True,
            "export_runtime": True,
            "activity_store": True,
            "transfer_runtime": True,
            "auth_dependency": True,
        },
    }


@pytest.mark.anyio
async def test_get_readiness_keeps_exports_ready_when_exports_disabled() -> (
    None
):
    """Exports-disabled deployments should not fail export readiness."""
    settings = _build_settings()
    settings.exports_enabled = False
    service = _build_service(
        settings=settings,
        authenticator=StubAuthenticator(),
    )

    response = await service.get_readiness()

    assert response.ok is True
    assert response.checks.export_runtime is True


@pytest.mark.anyio
async def test_get_readiness_does_not_gate_idempotency_when_disabled() -> None:
    """Idempotency outages stay diagnostic when idempotency is disabled."""
    settings = _build_settings()
    settings.idempotency_enabled = False
    service = _build_service(
        settings=settings,
        idempotency_store=_FailingIdempotencyStore(),
        authenticator=StubAuthenticator(),
    )

    response = await service.get_readiness()

    assert response.ok is True
    assert response.checks.idempotency_store is False


@pytest.mark.anyio
async def test_get_readiness_does_not_gate_transfer_when_disabled() -> None:
    """Disabled transfers should not gate readiness."""
    settings = _build_settings()
    settings.file_transfer_enabled = False
    service = _build_service(
        settings=settings,
        transfer_service=_FailingTransferService(),
        authenticator=StubAuthenticator(),
    )

    response = await service.get_readiness()

    assert response.ok is True
    assert response.checks.transfer_runtime is False


@pytest.mark.anyio
async def test_get_readiness_fails_when_required_probe_reports_false() -> None:
    """False transfer or auth probes should fail readiness."""
    service = _build_service(
        transfer_service=_FailingTransferService(),
        authenticator=_UnreadyAuthenticator(),
    )

    response = await service.get_readiness()

    assert response.ok is False
    assert response.checks.transfer_runtime is False
    assert response.checks.auth_dependency is False


@pytest.mark.anyio
async def test_get_readiness_fails_closed_when_auth_probe_raises() -> None:
    """Auth probe exceptions should fail readiness without bubbling."""
    service = _build_service(authenticator=_ExplodingAuthenticator())

    response = await service.get_readiness()

    assert response.ok is False
    assert response.checks.auth_dependency is False


@pytest.mark.anyio
async def test_get_readiness_reports_activity_store_failures() -> None:
    """Activity-store failures should remain diagnostic."""
    service = _build_service(
        activity_store=_FailingActivityStore(),
        authenticator=StubAuthenticator(),
    )

    response = await service.get_readiness()

    assert response.ok is True
    assert response.checks.activity_store is False


@pytest.mark.anyio
async def test_get_readiness_runs_independent_probes_concurrently() -> None:
    """Independent readiness probes should all start before any are released."""
    probes = [_GateProbe() for _ in range(6)]
    export_service = ExportService(
        repository=cast(ExportRepository, _GateRepository(probes[4])),
        publisher=cast(ExportPublisher, _GatePublisher(probes[5])),
        metrics=MetricsCollector(namespace="Tests"),
    )
    service = _build_service(
        idempotency_store=_GateIdempotencyStore(probes[0]),
        export_service=export_service,
        transfer_service=_GateTransferService(probes[1]),
        activity_store=_GateActivityStore(probes[2]),
        authenticator=_GateAuthenticator(probes[3]),
    )

    task = asyncio.create_task(service.get_readiness())
    try:
        await asyncio.wait_for(
            asyncio.gather(*(probe.started.wait() for probe in probes)),
            timeout=1.0,
        )
    finally:
        for probe in probes:
            probe.release.set()

    response = await asyncio.wait_for(task, timeout=1.0)

    assert response.ok is True


@pytest.mark.anyio
async def test_get_readiness_times_out_slow_transfer_probe() -> None:
    """Slow transfer probes should fail readiness instead of hanging."""
    service = _build_service(
        transfer_service=_GateTransferService(_GateProbe()),
        authenticator=StubAuthenticator(),
    )

    response = await asyncio.wait_for(service.get_readiness(), timeout=2.0)

    assert response.ok is False
    assert response.checks.transfer_runtime is False
