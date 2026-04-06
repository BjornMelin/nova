from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.capabilities_response import CapabilitiesResponse
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/capabilities",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CapabilitiesResponse | None:
    if response.status_code == 200:
        response_200 = CapabilitiesResponse.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CapabilitiesResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[CapabilitiesResponse]:
    """
    Get runtime capability declarations

    Expose the major runtime capabilities enabled for the current Nova
    deployment.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.

    Returns:
        Response[CapabilitiesResponse]: Detailed HTTP response wrapper
            containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> CapabilitiesResponse | None:
    """
    Get runtime capability declarations

    Expose the major runtime capabilities enabled for the current Nova
    deployment.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.

    Returns:
        CapabilitiesResponse | None: Parsed response payload, or ``None``
            when unexpected statuses are ignored by the client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[CapabilitiesResponse]:
    """
    Get runtime capability declarations

    Expose the major runtime capabilities enabled for the current Nova
    deployment.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.

    Returns:
        Response[CapabilitiesResponse]: Detailed HTTP response wrapper
            containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> CapabilitiesResponse | None:
    """
    Get runtime capability declarations

    Expose the major runtime capabilities enabled for the current Nova
    deployment.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.

    Returns:
        CapabilitiesResponse | None: Parsed response payload, or ``None``
            when unexpected statuses are ignored by the client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
