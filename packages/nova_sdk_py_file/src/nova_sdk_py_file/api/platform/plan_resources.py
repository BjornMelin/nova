# ruff: noqa
from typing import Any

import httpx

from nova_sdk_py_file import errors
from nova_sdk_py_file.client import AuthenticatedClient, Client
from nova_sdk_py_file.models.error_envelope import ErrorEnvelope
from nova_sdk_py_file.models.resource_plan_request import ResourcePlanRequest
from nova_sdk_py_file.models.resource_plan_response import ResourcePlanResponse
from nova_sdk_py_file.types import Response


def _get_kwargs(
    *,
    body: ResourcePlanRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/resources/plan",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorEnvelope | ResourcePlanResponse | None:
    if response.status_code == 200:
        response_200 = ResourcePlanResponse.from_dict(response.json())

        return response_200

    if response.status_code == 422:
        response_422 = ErrorEnvelope.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorEnvelope | ResourcePlanResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ResourcePlanRequest,
) -> Response[ErrorEnvelope | ResourcePlanResponse]:
    """Plan Resources

     Plan supportability for requested resource keys.

    Args:
        body (ResourcePlanRequest): Resource planning request body.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorEnvelope | ResourcePlanResponse]
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
    body: ResourcePlanRequest,
) -> ErrorEnvelope | ResourcePlanResponse | None:
    """Plan Resources

     Plan supportability for requested resource keys.

    Args:
        body (ResourcePlanRequest): Resource planning request body.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorEnvelope | ResourcePlanResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ResourcePlanRequest,
) -> Response[ErrorEnvelope | ResourcePlanResponse]:
    """Plan Resources

     Plan supportability for requested resource keys.

    Args:
        body (ResourcePlanRequest): Resource planning request body.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorEnvelope | ResourcePlanResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ResourcePlanRequest,
) -> ErrorEnvelope | ResourcePlanResponse | None:
    """Plan Resources

     Plan supportability for requested resource keys.

    Args:
        body (ResourcePlanRequest): Resource planning request body.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorEnvelope | ResourcePlanResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
