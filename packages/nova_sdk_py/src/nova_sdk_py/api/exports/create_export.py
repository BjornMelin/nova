from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.create_export_request import CreateExportRequest
from ...models.error_envelope import ErrorEnvelope
from ...models.export_resource import ExportResource
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: CreateExportRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/exports",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorEnvelope | ExportResource | None:
    if response.status_code == 201:
        response_201 = ExportResource.from_dict(response.json())

        return response_201

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
) -> Response[ErrorEnvelope | ExportResource]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: CreateExportRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> Response[ErrorEnvelope | ExportResource]:
    """
    Create an export workflow

    Create a caller-owned export resource that copies a source object into a
    download-oriented export output.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (CreateExportRequest): Request body payload for this operation.
        idempotency_key (None | str | Unset): Request option passed through
            to the generated client helper.

    Returns:
        Response[ErrorEnvelope | ExportResource]: Detailed HTTP response
            wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
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
    body: CreateExportRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> ErrorEnvelope | ExportResource | None:
    """
    Create an export workflow

    Create a caller-owned export resource that copies a source object into a
    download-oriented export output.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (CreateExportRequest): Request body payload for this operation.
        idempotency_key (None | str | Unset): Request option passed through
            to the generated client helper.

    Returns:
        ErrorEnvelope | ExportResource | None: Parsed response payload, or
            ``None`` when unexpected statuses are ignored by the client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return sync_detailed(
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: CreateExportRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> Response[ErrorEnvelope | ExportResource]:
    """
    Create an export workflow

    Create a caller-owned export resource that copies a source object into a
    download-oriented export output.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (CreateExportRequest): Request body payload for this operation.
        idempotency_key (None | str | Unset): Request option passed through
            to the generated client helper.

    Returns:
        Response[ErrorEnvelope | ExportResource]: Detailed HTTP response
            wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
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
    body: CreateExportRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> ErrorEnvelope | ExportResource | None:
    """
    Create an export workflow

    Create a caller-owned export resource that copies a source object into a
    download-oriented export output.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (CreateExportRequest): Request body payload for this operation.
        idempotency_key (None | str | Unset): Request option passed through
            to the generated client helper.

    Returns:
        ErrorEnvelope | ExportResource | None: Parsed response payload, or
            ``None`` when unexpected statuses are ignored by the client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
