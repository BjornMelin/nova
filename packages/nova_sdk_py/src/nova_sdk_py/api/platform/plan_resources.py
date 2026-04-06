from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_envelope import ErrorEnvelope
from ...models.resource_plan_request import ResourcePlanRequest
from ...models.resource_plan_response import ResourcePlanResponse
from ...types import Response


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
    """
    Plan resource support

    Report whether each requested resource is currently supported in the
    active deployment.
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
    """
    Plan resource support

    Report whether each requested resource is currently supported in the
    active deployment.
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
    """
    Plan resource support

    Report whether each requested resource is currently supported in the
    active deployment.
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
    """
    Plan resource support

    Report whether each requested resource is currently supported in the
    active deployment.
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
