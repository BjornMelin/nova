# ruff: noqa
from typing import Any

import httpx

from nova_sdk_py_auth import errors
from nova_sdk_py_auth.client import AuthenticatedClient, Client
from nova_sdk_py_auth.models.error_envelope import ErrorEnvelope
from nova_sdk_py_auth.models.token_introspect_form_request import (
    TokenIntrospectFormRequest,
)
from nova_sdk_py_auth.models.token_introspect_request import (
    TokenIntrospectRequest,
)
from nova_sdk_py_auth.models.token_introspect_response import (
    TokenIntrospectResponse,
)
from nova_sdk_py_auth.types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: TokenIntrospectRequest | TokenIntrospectFormRequest | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/token/introspect",
    }

    if isinstance(body, TokenIntrospectRequest):
        _kwargs["json"] = body.to_dict()

        headers["Content-Type"] = "application/json"
    elif isinstance(body, TokenIntrospectFormRequest):
        _kwargs["data"] = body.to_dict()

        headers["Content-Type"] = "application/x-www-form-urlencoded"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorEnvelope | TokenIntrospectResponse | None:
    if response.status_code == 200:
        response_200 = TokenIntrospectResponse.from_dict(response.json())

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
) -> Response[ErrorEnvelope | TokenIntrospectResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: TokenIntrospectRequest | TokenIntrospectFormRequest | Unset = UNSET,
) -> Response[ErrorEnvelope | TokenIntrospectResponse]:
    """Introspect Token

     Introspect token and return active status plus claim details.

    Args:
        body (TokenIntrospectRequest | TokenIntrospectFormRequest | Unset): Request payload for token introspection.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorEnvelope | TokenIntrospectResponse]
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
    client: AuthenticatedClient | Client,
    body: TokenIntrospectRequest | TokenIntrospectFormRequest | Unset = UNSET,
) -> ErrorEnvelope | TokenIntrospectResponse | None:
    """Introspect Token

     Introspect token and return active status plus claim details.

    Args:
        body (TokenIntrospectRequest | TokenIntrospectFormRequest | Unset): Request payload for token introspection.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorEnvelope | TokenIntrospectResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: TokenIntrospectRequest | TokenIntrospectFormRequest | Unset = UNSET,
) -> Response[ErrorEnvelope | TokenIntrospectResponse]:
    """Introspect Token

     Introspect token and return active status plus claim details.

    Args:
        body (TokenIntrospectRequest | TokenIntrospectFormRequest | Unset): Request payload for token introspection.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorEnvelope | TokenIntrospectResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: TokenIntrospectRequest | TokenIntrospectFormRequest | Unset = UNSET,
) -> ErrorEnvelope | TokenIntrospectResponse | None:
    """Introspect Token

     Introspect token and return active status plus claim details.

    Args:
        body (TokenIntrospectRequest | TokenIntrospectFormRequest | Unset): Request payload for token introspection.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorEnvelope | TokenIntrospectResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
