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
    Return the request identifier attached to request.state by middleware, if any.
    
    Returns:
        The request identifier string if present on request.state, otherwise None.
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
        Authenticate the current request's caller and return the resulting Principal.
        
        Parameters:
            session_id (str | None): Optional session identifier to use for authentication; pass None to authenticate without a session.
        
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
    Create a request-scoped runtime context for route handlers.
    
    Returns:
        RequestContext: A RequestContext containing the current Request and the resolved AppContainer.
    """
    return RequestContext(
        request=request,
        container=container,
    )


ContainerDep = Annotated[AppContainer, Depends(get_container)]
RequestContextDep = Annotated[RequestContext, Depends(get_request_context)]