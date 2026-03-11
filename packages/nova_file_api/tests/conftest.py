from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from nova_file_api.app import create_app
from nova_file_api.cache import SharedRedisCache, TwoTierCache
from nova_file_api.config import Settings
from nova_file_api.dependencies import (
    get_activity_store,
    get_authenticator,
    get_idempotency_store,
    get_job_repository,
    get_job_service,
    get_metrics,
    get_shared_cache,
    get_transfer_service,
    get_two_tier_cache,
)
from nova_file_api.idempotency import IdempotencyStore
from nova_file_api.metrics import MetricsCollector

from ._test_doubles import StubAuthenticator, StubTransferService


@dataclass(slots=True)
class RuntimeDeps:
    """Explicit test doubles installed through FastAPI dependency overrides."""

    settings: Settings
    metrics: MetricsCollector
    shared_cache: SharedRedisCache
    cache: TwoTierCache
    authenticator: Any
    transfer_service: Any
    job_service: Any
    activity_store: Any
    idempotency_store: IdempotencyStore
    job_repository: Any | None = None


@pytest.fixture(autouse=True)
def aws_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide inert AWS defaults so app lifespan can build local clients."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


@pytest.fixture
def stub_authenticator() -> StubAuthenticator:
    return StubAuthenticator()


@pytest.fixture
def stub_transfer_service() -> StubTransferService:
    return StubTransferService()


def build_test_app(deps: RuntimeDeps) -> FastAPI:
    """Create an app and install explicit dependency overrides."""
    app = create_app()
    app.state.settings = deps.settings
    app.dependency_overrides[get_metrics] = lambda: deps.metrics
    app.dependency_overrides[get_shared_cache] = lambda: deps.shared_cache
    app.dependency_overrides[get_two_tier_cache] = lambda: deps.cache
    app.dependency_overrides[get_authenticator] = lambda: deps.authenticator
    app.dependency_overrides[get_transfer_service] = lambda: (
        deps.transfer_service
    )
    if deps.job_repository is not None:
        app.dependency_overrides[get_job_repository] = lambda: (
            deps.job_repository
        )
    app.dependency_overrides[get_job_service] = lambda: deps.job_service
    app.dependency_overrides[get_activity_store] = lambda: deps.activity_store
    app.dependency_overrides[get_idempotency_store] = lambda: (
        deps.idempotency_store
    )
    return app
