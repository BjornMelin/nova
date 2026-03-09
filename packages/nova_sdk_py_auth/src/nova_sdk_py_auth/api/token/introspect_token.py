from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.token_introspect_form_request import TokenIntrospectFormRequest
from ...models.token_introspect_request import TokenIntrospectRequest
from ...models.token_introspect_response import TokenIntrospectResponse
from ...types import Response


def _get_kwargs(
    *,
    body: TokenIntrospectRequest | TokenIntrospectFormRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/token/introspect",
    }

    if isinstance(body, TokenIntrospectRequest):
        _kwargs["json"] = body.to_dict()

        headers["Content-Type"] = "application/json"
    if isinstance(body, TokenIntrospectFormRequest):
        _kwargs["data"] = body.to_dict()

        headers["Content-Type"] = "application/x-www-form-urlencoded"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> TokenIntrospectResponse | None:
    if response.status_code == 200:
        response_200 = TokenIntrospectResponse.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[TokenIntrospectResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: TokenIntrospectRequest | TokenIntrospectFormRequest,
) -> Response[TokenIntrospectResponse]:
    """Introspect Token

     Introspect token and return active status plus claim details.

    Args:
        body (TokenIntrospectRequest): Request payload for token introspection.
        body (TokenIntrospectFormRequest): Request payload for token introspection.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[TokenIntrospectResponse]
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
    body: TokenIntrospectRequest | TokenIntrospectFormRequest,
) -> TokenIntrospectResponse | None:
    """Introspect Token

     Introspect token and return active status plus claim details.

    Args:
        body (TokenIntrospectRequest): Request payload for token introspection.
        body (TokenIntrospectFormRequest): Request payload for token introspection.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        TokenIntrospectResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: TokenIntrospectRequest | TokenIntrospectFormRequest,
) -> Response[TokenIntrospectResponse]:
    """Introspect Token

     Introspect token and return active status plus claim details.

    Args:
        body (TokenIntrospectRequest): Request payload for token introspection.
        body (TokenIntrospectFormRequest): Request payload for token introspection.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[TokenIntrospectResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: TokenIntrospectRequest | TokenIntrospectFormRequest,
) -> TokenIntrospectResponse | None:
    """Introspect Token

     Introspect token and return active status plus claim details.

    Args:
        body (TokenIntrospectRequest): Request payload for token introspection.
        body (TokenIntrospectFormRequest): Request payload for token introspection.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        TokenIntrospectResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
