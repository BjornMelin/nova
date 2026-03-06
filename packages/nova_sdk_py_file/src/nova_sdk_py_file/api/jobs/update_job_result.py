from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.job_result_update_request import JobResultUpdateRequest
from ...models.job_result_update_response import JobResultUpdateResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    job_id: str,
    *,
    body: JobResultUpdateRequest,
    x_worker_token: None | str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_worker_token, Unset):
        headers["X-Worker-Token"] = x_worker_token

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/internal/jobs/{job_id}/result".format(
            job_id=quote(str(job_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | JobResultUpdateResponse | None:
    if response.status_code == 200:
        response_200 = JobResultUpdateResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | JobResultUpdateResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    job_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: JobResultUpdateRequest,
    x_worker_token: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | JobResultUpdateResponse]:
    """Update Job Result

     Update job status/result from trusted worker-side processing.

    Args:
        job_id (str):
        x_worker_token (None | str | Unset):
        body (JobResultUpdateRequest): Worker/internal request payload for job result updates.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | JobResultUpdateResponse]
    """

    kwargs = _get_kwargs(
        job_id=job_id,
        body=body,
        x_worker_token=x_worker_token,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    job_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: JobResultUpdateRequest,
    x_worker_token: None | str | Unset = UNSET,
) -> HTTPValidationError | JobResultUpdateResponse | None:
    """Update Job Result

     Update job status/result from trusted worker-side processing.

    Args:
        job_id (str):
        x_worker_token (None | str | Unset):
        body (JobResultUpdateRequest): Worker/internal request payload for job result updates.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | JobResultUpdateResponse
    """

    return sync_detailed(
        job_id=job_id,
        client=client,
        body=body,
        x_worker_token=x_worker_token,
    ).parsed


async def asyncio_detailed(
    job_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: JobResultUpdateRequest,
    x_worker_token: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | JobResultUpdateResponse]:
    """Update Job Result

     Update job status/result from trusted worker-side processing.

    Args:
        job_id (str):
        x_worker_token (None | str | Unset):
        body (JobResultUpdateRequest): Worker/internal request payload for job result updates.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | JobResultUpdateResponse]
    """

    kwargs = _get_kwargs(
        job_id=job_id,
        body=body,
        x_worker_token=x_worker_token,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    job_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: JobResultUpdateRequest,
    x_worker_token: None | str | Unset = UNSET,
) -> HTTPValidationError | JobResultUpdateResponse | None:
    """Update Job Result

     Update job status/result from trusted worker-side processing.

    Args:
        job_id (str):
        x_worker_token (None | str | Unset):
        body (JobResultUpdateRequest): Worker/internal request payload for job result updates.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | JobResultUpdateResponse
    """

    return (
        await asyncio_detailed(
            job_id=job_id,
            client=client,
            body=body,
            x_worker_token=x_worker_token,
        )
    ).parsed
