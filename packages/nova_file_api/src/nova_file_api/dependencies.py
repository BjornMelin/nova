"""FastAPI dependency helpers."""

from __future__ import annotations

from fastapi import Request

from nova_file_api.container import AppContainer

_APPLICATION_CONTAINER_NOT_INITIALIZED = (
    "application container is not initialized"
)


def get_container(request: Request) -> AppContainer:
    """Return dependency container from app state."""
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, AppContainer):
        raise TypeError(_APPLICATION_CONTAINER_NOT_INITIALIZED)
    return container


def get_request_id(request: Request) -> str | None:
    """Return request-id value from middleware state."""
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str):
        return value
    return None
