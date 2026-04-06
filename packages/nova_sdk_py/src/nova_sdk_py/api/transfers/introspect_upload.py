from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_envelope import ErrorEnvelope
from ...models.upload_introspection_request import UploadIntrospectionRequest
from ...models.upload_introspection_response import UploadIntrospectionResponse
from ...types import Response


def _get_kwargs(
    *,
    body: UploadIntrospectionRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/transfers/uploads/introspect",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorEnvelope | UploadIntrospectionResponse | None:
    if response.status_code == 200:
        response_200 = UploadIntrospectionResponse.from_dict(response.json())

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
) -> Response[ErrorEnvelope | UploadIntrospectionResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: UploadIntrospectionRequest,
) -> Response[ErrorEnvelope | UploadIntrospectionResponse]:
    """
    Inspect multipart upload state

    Return the persisted multipart session state so browser or native
    clients can resume an interrupted upload.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (UploadIntrospectionRequest): Request body payload for this
            operation.

    Returns:
        Response[ErrorEnvelope | UploadIntrospectionResponse]: Detailed HTTP
            response wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
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
    body: UploadIntrospectionRequest,
) -> ErrorEnvelope | UploadIntrospectionResponse | None:
    """
    Inspect multipart upload state

    Return the persisted multipart session state so browser or native
    clients can resume an interrupted upload.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (UploadIntrospectionRequest): Request body payload for this
            operation.

    Returns:
        ErrorEnvelope | UploadIntrospectionResponse | None: Parsed response
            payload, or ``None`` when unexpected statuses are ignored by the
            client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: UploadIntrospectionRequest,
) -> Response[ErrorEnvelope | UploadIntrospectionResponse]:
    """
    Inspect multipart upload state

    Return the persisted multipart session state so browser or native
    clients can resume an interrupted upload.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (UploadIntrospectionRequest): Request body payload for this
            operation.

    Returns:
        Response[ErrorEnvelope | UploadIntrospectionResponse]: Detailed HTTP
            response wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: UploadIntrospectionRequest,
) -> ErrorEnvelope | UploadIntrospectionResponse | None:
    """
    Inspect multipart upload state

    Return the persisted multipart session state so browser or native
    clients can resume an interrupted upload.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (UploadIntrospectionRequest): Request body payload for this
            operation.

    Returns:
        ErrorEnvelope | UploadIntrospectionResponse | None: Parsed response
            payload, or ``None`` when unexpected statuses are ignored by the
            client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
