# ruff: noqa
"""Client helpers for the `/v1/releases/info` endpoint.

Functions in this module use AuthenticatedClient/Client and
raise ``errors.UnexpectedStatus`` for undocumented responses."""

from typing import Any

import httpx

from nova_sdk_py_file import errors
from nova_sdk_py_file.client import AuthenticatedClient, Client
from nova_sdk_py_file.models.release_info_response import ReleaseInfoResponse
from nova_sdk_py_file.types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/releases/info",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ReleaseInfoResponse | None:
    if response.status_code == 200:
        response_200 = ReleaseInfoResponse.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ReleaseInfoResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ReleaseInfoResponse]:
    """Get Release Info

     Return service release metadata.

    Args:
        client (AuthenticatedClient | Client): Configured API client.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented
            status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than
            Client.timeout.

    Returns:
        Response[ReleaseInfoResponse]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> ReleaseInfoResponse | None:
    """Get Release Info

     Return service release metadata.

    Args:
        client (AuthenticatedClient | Client): Configured API client.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented
            status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than
            Client.timeout.

    Returns:
        ReleaseInfoResponse | None
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ReleaseInfoResponse]:
    """Get Release Info

     Return service release metadata.

    Args:
        client (AuthenticatedClient | Client): Configured API client.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented
            status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than
            Client.timeout.

    Returns:
        Response[ReleaseInfoResponse]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> ReleaseInfoResponse | None:
    """Get Release Info

     Return service release metadata.

    Args:
        client (AuthenticatedClient | Client): Configured API client.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented
            status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than
            Client.timeout.

    Returns:
        ReleaseInfoResponse | None
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
