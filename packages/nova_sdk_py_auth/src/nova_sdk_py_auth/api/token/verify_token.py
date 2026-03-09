# ruff: noqa
from http import HTTPStatus
from typing import Any

import httpx

from nova_sdk_py_auth import errors
from nova_sdk_py_auth.client import AuthenticatedClient, Client
from nova_sdk_py_auth.models.error_envelope import ErrorEnvelope
from nova_sdk_py_auth.models.token_verify_request import TokenVerifyRequest
from nova_sdk_py_auth.models.token_verify_response import TokenVerifyResponse
from nova_sdk_py_auth.types import Response


def _get_kwargs(
    *,
    body: TokenVerifyRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/token/verify",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorEnvelope | TokenVerifyResponse | None:
    if response.status_code == 200:
        response_200 = TokenVerifyResponse.from_dict(response.json())

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
) -> Response[ErrorEnvelope | TokenVerifyResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: TokenVerifyRequest,
) -> Response[ErrorEnvelope | TokenVerifyResponse]:
    """Verify Token

     Verify access token and return principal plus claims.

    Args:
        body (TokenVerifyRequest): Request payload for access token verification.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorEnvelope | TokenVerifyResponse]
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
    body: TokenVerifyRequest,
) -> ErrorEnvelope | TokenVerifyResponse | None:
    """Verify Token

     Verify access token and return principal plus claims.

    Args:
        body (TokenVerifyRequest): Request payload for access token verification.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorEnvelope | TokenVerifyResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: TokenVerifyRequest,
) -> Response[ErrorEnvelope | TokenVerifyResponse]:
    """Verify Token

     Verify access token and return principal plus claims.

    Args:
        body (TokenVerifyRequest): Request payload for access token verification.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorEnvelope | TokenVerifyResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: TokenVerifyRequest,
) -> ErrorEnvelope | TokenVerifyResponse | None:
    """Verify Token

     Verify access token and return principal plus claims.

    Args:
        body (TokenVerifyRequest): Request payload for access token verification.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorEnvelope | TokenVerifyResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
