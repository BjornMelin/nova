from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_envelope import ErrorEnvelope
from ...models.export_list_response import ExportListResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    limit: int | Unset = 50,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["limit"] = limit

    params = {
        k: v for k, v in params.items() if v is not UNSET and v is not None
    }

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/exports",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorEnvelope | ExportListResponse | None:
    if response.status_code == 200:
        response_200 = ExportListResponse.from_dict(response.json())

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
) -> Response[ErrorEnvelope | ExportListResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    limit: int | Unset = 50,
) -> Response[ErrorEnvelope | ExportListResponse]:
    """
    List export workflows

    List caller-owned export workflow resources with the most recent exports
    first.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        limit (int | Unset): Maximum number of caller-owned export workflow
            resources to return, ordered newest first.

    Returns:
        Response[ErrorEnvelope | ExportListResponse]: Detailed HTTP response
            wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    kwargs = _get_kwargs(
        limit=limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    limit: int | Unset = 50,
) -> ErrorEnvelope | ExportListResponse | None:
    """
    List export workflows

    List caller-owned export workflow resources with the most recent exports
    first.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        limit (int | Unset): Maximum number of caller-owned export workflow
            resources to return, ordered newest first.

    Returns:
        ErrorEnvelope | ExportListResponse | None: Parsed response payload,
            or ``None`` when unexpected statuses are ignored by the client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return sync_detailed(
        client=client,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    limit: int | Unset = 50,
) -> Response[ErrorEnvelope | ExportListResponse]:
    """
    List export workflows

    List caller-owned export workflow resources with the most recent exports
    first.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        limit (int | Unset): Maximum number of caller-owned export workflow
            resources to return, ordered newest first.

    Returns:
        Response[ErrorEnvelope | ExportListResponse]: Detailed HTTP response
            wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    kwargs = _get_kwargs(
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    limit: int | Unset = 50,
) -> ErrorEnvelope | ExportListResponse | None:
    """
    List export workflows

    List caller-owned export workflow resources with the most recent exports
    first.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        limit (int | Unset): Maximum number of caller-owned export workflow
            resources to return, ordered newest first.

    Returns:
        ErrorEnvelope | ExportListResponse | None: Parsed response payload,
            or ``None`` when unexpected statuses are ignored by the client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return (
        await asyncio_detailed(
            client=client,
            limit=limit,
        )
    ).parsed
