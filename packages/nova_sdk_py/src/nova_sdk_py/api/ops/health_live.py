from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.health_response import HealthResponse
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/health/live",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HealthResponse | None:
    if response.status_code == 200:
        response_200 = HealthResponse.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[HealthResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[HealthResponse]:
    """
    Check liveness

    Return a shallow liveness signal for the API runtime process.
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> HealthResponse | None:
    """
    Check liveness

    Return a shallow liveness signal for the API runtime process.
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[HealthResponse]:
    """
    Check liveness

    Return a shallow liveness signal for the API runtime process.
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> HealthResponse | None:
    """
    Check liveness

    Return a shallow liveness signal for the API runtime process.
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
