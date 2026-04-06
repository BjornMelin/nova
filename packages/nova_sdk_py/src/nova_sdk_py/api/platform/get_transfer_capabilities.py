from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.transfer_capabilities_response import (
    TransferCapabilitiesResponse,
)
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    workload_class: None | str | Unset = UNSET,
    policy_hint: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_workload_class: None | str | Unset
    if isinstance(workload_class, Unset):
        json_workload_class = UNSET
    else:
        json_workload_class = workload_class
    params["workload_class"] = json_workload_class

    json_policy_hint: None | str | Unset
    if isinstance(policy_hint, Unset):
        json_policy_hint = UNSET
    else:
        json_policy_hint = policy_hint
    params["policy_hint"] = json_policy_hint

    params = {
        k: v for k, v in params.items() if v is not UNSET and v is not None
    }

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/capabilities/transfers",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | TransferCapabilitiesResponse | None:
    if response.status_code == 200:
        response_200 = TransferCapabilitiesResponse.from_dict(response.json())

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[HTTPValidationError | TransferCapabilitiesResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    workload_class: None | str | Unset = UNSET,
    policy_hint: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | TransferCapabilitiesResponse]:
    """
    Get the effective transfer policy

    Expose the current transfer policy envelope that browser and native
    upload clients should honor.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.
        workload_class (None | str | Unset): Optional workload-class hint
            used to resolve a narrower effective transfer policy.
        policy_hint (None | str | Unset): Optional policy hint evaluated by
            the transfer policy resolver.

    Returns:
        Response[HTTPValidationError | TransferCapabilitiesResponse]: Detailed
            HTTP response wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    kwargs = _get_kwargs(
        workload_class=workload_class,
        policy_hint=policy_hint,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    workload_class: None | str | Unset = UNSET,
    policy_hint: None | str | Unset = UNSET,
) -> HTTPValidationError | TransferCapabilitiesResponse | None:
    """
    Get the effective transfer policy

    Expose the current transfer policy envelope that browser and native
    upload clients should honor.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.
        workload_class (None | str | Unset): Optional workload-class hint
            used to resolve a narrower effective transfer policy.
        policy_hint (None | str | Unset): Optional policy hint evaluated by
            the transfer policy resolver.

    Returns:
        HTTPValidationError | TransferCapabilitiesResponse | None: Parsed
            response payload, or ``None`` when unexpected statuses are
            ignored by the client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return sync_detailed(
        client=client,
        workload_class=workload_class,
        policy_hint=policy_hint,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    workload_class: None | str | Unset = UNSET,
    policy_hint: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | TransferCapabilitiesResponse]:
    """
    Get the effective transfer policy

    Expose the current transfer policy envelope that browser and native
    upload clients should honor.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.
        workload_class (None | str | Unset): Optional workload-class hint
            used to resolve a narrower effective transfer policy.
        policy_hint (None | str | Unset): Optional policy hint evaluated by
            the transfer policy resolver.

    Returns:
        Response[HTTPValidationError | TransferCapabilitiesResponse]: Detailed
            HTTP response wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    kwargs = _get_kwargs(
        workload_class=workload_class,
        policy_hint=policy_hint,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    workload_class: None | str | Unset = UNSET,
    policy_hint: None | str | Unset = UNSET,
) -> HTTPValidationError | TransferCapabilitiesResponse | None:
    """
    Get the effective transfer policy

    Expose the current transfer policy envelope that browser and native
    upload clients should honor.

    Args:
        client (AuthenticatedClient | Client): SDK client used to send the
            request and parse the response.
        workload_class (None | str | Unset): Optional workload-class hint
            used to resolve a narrower effective transfer policy.
        policy_hint (None | str | Unset): Optional policy hint evaluated by
            the transfer policy resolver.

    Returns:
        HTTPValidationError | TransferCapabilitiesResponse | None: Parsed
            response payload, or ``None`` when unexpected statuses are
            ignored by the client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return (
        await asyncio_detailed(
            client=client,
            workload_class=workload_class,
            policy_hint=policy_hint,
        )
    ).parsed
