from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_envelope import ErrorEnvelope
from ...models.export_resource import ExportResource
from ...types import Response


def _get_kwargs(
    export_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/exports/{export_id}/cancel".format(
            export_id=quote(str(export_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorEnvelope | ExportResource | None:
    if response.status_code == 200:
        response_200 = ExportResource.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = ErrorEnvelope.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorEnvelope.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorEnvelope.from_dict(response.json())

        return response_404

    if response.status_code == 422:
        response_422 = ErrorEnvelope.from_dict(response.json())

        return response_422

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
    export_id: str,
    *,
    client: AuthenticatedClient,
) -> Response[ErrorEnvelope | ExportResource]:
    """
    Cancel an export workflow

    Persist cancel intent for a caller-owned export that has not yet reached
    a terminal state.

    Args:
        export_id (str): Identifier of the caller-owned export workflow
            resource.
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.

    Returns:
        Response[ErrorEnvelope | ExportResource]: Detailed HTTP response
            wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    kwargs = _get_kwargs(
        export_id=export_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    export_id: str,
    *,
    client: AuthenticatedClient,
) -> ErrorEnvelope | ExportResource | None:
    """
    Cancel an export workflow

    Persist cancel intent for a caller-owned export that has not yet reached
    a terminal state.

    Args:
        export_id (str): Identifier of the caller-owned export workflow
            resource.
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.

    Returns:
        ErrorEnvelope | ExportResource | None: Parsed response payload, or
            ``None`` when unexpected statuses are ignored by the client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return sync_detailed(
        export_id=export_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    export_id: str,
    *,
    client: AuthenticatedClient,
) -> Response[ErrorEnvelope | ExportResource]:
    """
    Cancel an export workflow

    Persist cancel intent for a caller-owned export that has not yet reached
    a terminal state.

    Args:
        export_id (str): Identifier of the caller-owned export workflow
            resource.
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.

    Returns:
        Response[ErrorEnvelope | ExportResource]: Detailed HTTP response
            wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    kwargs = _get_kwargs(
        export_id=export_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    export_id: str,
    *,
    client: AuthenticatedClient,
) -> ErrorEnvelope | ExportResource | None:
    """
    Cancel an export workflow

    Persist cancel intent for a caller-owned export that has not yet reached
    a terminal state.

    Args:
        export_id (str): Identifier of the caller-owned export workflow
            resource.
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.

    Returns:
        ErrorEnvelope | ExportResource | None: Parsed response payload, or
            ``None`` when unexpected statuses are ignored by the client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return (
        await asyncio_detailed(
            export_id=export_id,
            client=client,
        )
    ).parsed
