from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.initiate_upload_request import InitiateUploadRequest
from ...models.initiate_upload_response import InitiateUploadResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: InitiateUploadRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset) and idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/transfers/uploads/initiate",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> InitiateUploadResponse | None:
    if response.status_code == 200:
        response_200 = InitiateUploadResponse.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[InitiateUploadResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: InitiateUploadRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> Response[InitiateUploadResponse]:
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[InitiateUploadResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: InitiateUploadRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> InitiateUploadResponse | None:
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        InitiateUploadResponse
    """

    return sync_detailed(
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: InitiateUploadRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> Response[InitiateUploadResponse]:
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[InitiateUploadResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: InitiateUploadRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> InitiateUploadResponse | None:
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        InitiateUploadResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
