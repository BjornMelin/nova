from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.release_info_response import ReleaseInfoResponse
from ...types import Response


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
    """
    Get public release metadata

    Return public release metadata used by browser clients, diagnostics, and
    deploy canaries.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.

    Returns:
        Response[ReleaseInfoResponse]: Detailed HTTP response wrapper
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
) -> ReleaseInfoResponse | None:
    """
    Get public release metadata

    Return public release metadata used by browser clients, diagnostics, and
    deploy canaries.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.

    Returns:
        ReleaseInfoResponse | None: Parsed response payload, or ``None``
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
) -> Response[ReleaseInfoResponse]:
    """
    Get public release metadata

    Return public release metadata used by browser clients, diagnostics, and
    deploy canaries.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.

    Returns:
        Response[ReleaseInfoResponse]: Detailed HTTP response wrapper
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
) -> ReleaseInfoResponse | None:
    """
    Get public release metadata

    Return public release metadata used by browser clients, diagnostics, and
    deploy canaries.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.

    Returns:
        ReleaseInfoResponse | None: Parsed response payload, or ``None``
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
