from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_envelope import ErrorEnvelope
from ...models.presign_download_request import PresignDownloadRequest
from ...models.presign_download_response import PresignDownloadResponse
from ...types import Response


def _get_kwargs(
    *,
    body: PresignDownloadRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/transfers/downloads/presign",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorEnvelope | PresignDownloadResponse | None:
    if response.status_code == 200:
        response_200 = PresignDownloadResponse.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = ErrorEnvelope.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorEnvelope.from_dict(response.json())

        return response_403

    if response.status_code == 422:
        response_422 = ErrorEnvelope.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorEnvelope | PresignDownloadResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: PresignDownloadRequest,
) -> Response[ErrorEnvelope | PresignDownloadResponse]:
    """
    Presign a direct download

    Return a time-limited download URL for an object the caller is
    authorized to access.
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    body: PresignDownloadRequest,
) -> ErrorEnvelope | PresignDownloadResponse | None:
    """
    Presign a direct download

    Return a time-limited download URL for an object the caller is
    authorized to access.
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: PresignDownloadRequest,
) -> Response[ErrorEnvelope | PresignDownloadResponse]:
    """
    Presign a direct download

    Return a time-limited download URL for an object the caller is
    authorized to access.
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: PresignDownloadRequest,
) -> ErrorEnvelope | PresignDownloadResponse | None:
    """
    Presign a direct download

    Return a time-limited download URL for an object the caller is
    authorized to access.
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
