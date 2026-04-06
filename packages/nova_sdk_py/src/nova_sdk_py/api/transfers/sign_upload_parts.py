from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_envelope import ErrorEnvelope
from ...models.sign_parts_request import SignPartsRequest
from ...models.sign_parts_response import SignPartsResponse
from ...types import Response


def _get_kwargs(
    *,
    body: SignPartsRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/transfers/uploads/sign-parts",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorEnvelope | SignPartsResponse | None:
    if response.status_code == 200:
        response_200 = SignPartsResponse.from_dict(response.json())

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
) -> Response[ErrorEnvelope | SignPartsResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: SignPartsRequest,
) -> Response[ErrorEnvelope | SignPartsResponse]:
    """
    Sign multipart upload parts

    Return presigned URLs for the requested multipart upload part numbers.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (SignPartsRequest): Request body payload for this operation.

    Returns:
        Response[ErrorEnvelope | SignPartsResponse]: Detailed HTTP response
            wrapper containing the parsed response payload.

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
    body: SignPartsRequest,
) -> ErrorEnvelope | SignPartsResponse | None:
    """
    Sign multipart upload parts

    Return presigned URLs for the requested multipart upload part numbers.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (SignPartsRequest): Request body payload for this operation.

    Returns:
        ErrorEnvelope | SignPartsResponse | None: Parsed response payload,
            or ``None`` when unexpected statuses are ignored by the client.

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
    body: SignPartsRequest,
) -> Response[ErrorEnvelope | SignPartsResponse]:
    """
    Sign multipart upload parts

    Return presigned URLs for the requested multipart upload part numbers.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (SignPartsRequest): Request body payload for this operation.

    Returns:
        Response[ErrorEnvelope | SignPartsResponse]: Detailed HTTP response
            wrapper containing the parsed response payload.

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
    body: SignPartsRequest,
) -> ErrorEnvelope | SignPartsResponse | None:
    """
    Sign multipart upload parts

    Return presigned URLs for the requested multipart upload part numbers.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.
        body (SignPartsRequest): Request body payload for this operation.

    Returns:
        ErrorEnvelope | SignPartsResponse | None: Parsed response payload,
            or ``None`` when unexpected statuses are ignored by the client.

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
