# ruff: noqa
from http import HTTPStatus
from typing import Any

import httpx

from nova_sdk_py_file import errors
from nova_sdk_py_file.client import AuthenticatedClient, Client
from nova_sdk_py_file.models.error_envelope import ErrorEnvelope
from nova_sdk_py_file.models.initiate_upload_request import (
    InitiateUploadRequest,
)
from nova_sdk_py_file.models.initiate_upload_response_type_0 import (
    InitiateUploadResponseType0,
)
from nova_sdk_py_file.models.initiate_upload_response_type_1 import (
    InitiateUploadResponseType1,
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
) -> (
    ErrorEnvelope
    | InitiateUploadResponseType0
    | InitiateUploadResponseType1
    | None
):
    if response.status_code == 200:

        def _parse_response_200(
            data: object,
        ) -> InitiateUploadResponseType0 | InitiateUploadResponseType1:
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_initiate_upload_response_type_0 = (
                    InitiateUploadResponseType0.from_dict(data)
                )

                return componentsschemas_initiate_upload_response_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            if not isinstance(data, dict):
                raise TypeError()
            componentsschemas_initiate_upload_response_type_1 = (
                InitiateUploadResponseType1.from_dict(data)
            )

            return componentsschemas_initiate_upload_response_type_1

        response_200 = _parse_response_200(response.json())

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

    if response.status_code == 503:
        response_503 = ErrorEnvelope.from_dict(response.json())

        return response_503

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    ErrorEnvelope | InitiateUploadResponseType0 | InitiateUploadResponseType1
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: InitiateUploadRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> Response[
    ErrorEnvelope | InitiateUploadResponseType0 | InitiateUploadResponseType1
]:
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorEnvelope | InitiateUploadResponseType0 | InitiateUploadResponseType1]
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
) -> (
    ErrorEnvelope
    | InitiateUploadResponseType0
    | InitiateUploadResponseType1
    | None
):
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorEnvelope | InitiateUploadResponseType0 | InitiateUploadResponseType1
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
) -> Response[
    ErrorEnvelope | InitiateUploadResponseType0 | InitiateUploadResponseType1
]:
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorEnvelope | InitiateUploadResponseType0 | InitiateUploadResponseType1]
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
) -> (
    ErrorEnvelope
    | InitiateUploadResponseType0
    | InitiateUploadResponseType1
    | None
):
    """Initiate Upload

     Choose upload strategy and return presigned metadata.

    Args:
        idempotency_key (None | str | Unset):
        body (InitiateUploadRequest): Initiate-upload request model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorEnvelope | InitiateUploadResponseType0 | InitiateUploadResponseType1
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
