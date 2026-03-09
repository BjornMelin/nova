# ruff: noqa
"""Client helpers for the `/v1/transfers/uploads/initiate` endpoint."""

from typing import Any

import httpx

from nova_sdk_py_file import errors
from nova_sdk_py_file.client import AuthenticatedClient, Client
from nova_sdk_py_file.models.error_envelope import ErrorEnvelope
from nova_sdk_py_file.models.initiate_upload_request import (
    InitiateUploadRequest,
)
from nova_sdk_py_file.models.initiate_upload_response import (
    InitiateUploadResponse,
)
from nova_sdk_py_file.types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: InitiateUploadRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
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
) -> ErrorEnvelope | InitiateUploadResponse | None:
    if response.status_code == 200:
        response_200 = InitiateUploadResponse.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = ErrorEnvelope.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorEnvelope.from_dict(response.json())

        return response_403

    if response.status_code == 409:
        response_409 = ErrorEnvelope.from_dict(response.json())

        return response_409

    if response.status_code == 422:
        response_422 = ErrorEnvelope.from_dict(response.json())

        return response_422

    if response.status_code == 503:
        response_503 = ErrorEnvelope.from_dict(response.json())

        return response_503

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorEnvelope | InitiateUploadResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: InitiateUploadRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> Response[ErrorEnvelope | InitiateUploadResponse]:
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorEnvelope | InitiateUploadResponse]
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
    client: AuthenticatedClient,
    body: InitiateUploadRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> ErrorEnvelope | InitiateUploadResponse | None:
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorEnvelope | InitiateUploadResponse | None
    """

    return sync_detailed(
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: InitiateUploadRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> Response[ErrorEnvelope | InitiateUploadResponse]:
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorEnvelope | InitiateUploadResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: InitiateUploadRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> ErrorEnvelope | InitiateUploadResponse | None:
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorEnvelope | InitiateUploadResponse | None
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
