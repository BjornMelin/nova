"""FastAPI dependency helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from nova_file_api.container import AppContainer
from nova_file_api.models import Principal

_APPLICATION_CONTAINER_NOT_INITIALIZED = (
    "application container is not initialized"
)


def get_container(request: Request) -> AppContainer:
    """
    Retrieve the application container stored on the FastAPI app state.
    
    Returns:
        AppContainer: The application's container instance.
    
    Raises:
        TypeError: If the container is missing or is not an AppContainer.
    """
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, AppContainer):
        raise TypeError(_APPLICATION_CONTAINER_NOT_INITIALIZED)
    return container


def get_request_id(request: Request) -> str | None:
    """
    Retrieve the request identifier set by middleware, if present.
    
    Returns:
        `str` if a `request_id` string is stored on request.state, `None` otherwise.
    """
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str):
        return value
    return None


@dataclass(slots=True)
class RequestContext:
    """Bundle request-scoped dependencies shared by route handlers."""

    request: Request
    container: AppContainer

    async def authenticate(self, *, session_id: str | None) -> Principal:
        """
        Authenticate the request's caller and return their principal.
        
        Parameters:
            session_id (str | None): Optional session identifier to authenticate (or None to authenticate without a session).
        
        Returns:
            Principal: The authenticated principal for the current request.
        """
        return await self.container.authenticator.authenticate(
            request=self.request,
            session_id=session_id,
        )


def get_request_context(
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> RequestContext:
    """
    Provide a request-scoped runtime context for route handlers.
    
    Returns:
        RequestContext: The context containing the current Request and the resolved application container.
    """
    return RequestContext(
        request=request,
        container=container,
    )


ContainerDep = Annotated[AppContainer, Depends(get_container)]
RequestContextDep = Annotated[RequestContext, Depends(get_request_context)]
