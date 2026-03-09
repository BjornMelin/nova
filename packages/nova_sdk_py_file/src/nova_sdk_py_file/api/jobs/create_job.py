from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.enqueue_job_request import EnqueueJobRequest
from ...models.enqueue_job_response import EnqueueJobResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: EnqueueJobRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/jobs",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> EnqueueJobResponse | None:
    if response.status_code == 200:
        response_200 = EnqueueJobResponse.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[EnqueueJobResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: EnqueueJobRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> Response[EnqueueJobResponse]:
    """Create Job

     Enqueue async processing job and return job id.

    Args:
        idempotency_key (None | str | Unset):
        body (EnqueueJobRequest): Request payload for job enqueue endpoint.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EnqueueJobResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: EnqueueJobRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> EnqueueJobResponse | None:
    """Create Job

     Enqueue async processing job and return job id.

    Args:
        idempotency_key (None | str | Unset):
        body (EnqueueJobRequest): Request payload for job enqueue endpoint.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EnqueueJobResponse
    """

    return sync_detailed(
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: EnqueueJobRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> Response[EnqueueJobResponse]:
    """Create Job

     Enqueue async processing job and return job id.

    Args:
        idempotency_key (None | str | Unset):
        body (EnqueueJobRequest): Request payload for job enqueue endpoint.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EnqueueJobResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: EnqueueJobRequest,
    idempotency_key: None | str | Unset = UNSET,
) -> EnqueueJobResponse | None:
    """Create Job

     Enqueue async processing job and return job id.

    Args:
        idempotency_key (None | str | Unset):
        body (EnqueueJobRequest): Request payload for job enqueue endpoint.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EnqueueJobResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
