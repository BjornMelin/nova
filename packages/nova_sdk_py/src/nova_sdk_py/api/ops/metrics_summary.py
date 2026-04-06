from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_envelope import ErrorEnvelope
from ...models.metrics_summary_response import MetricsSummaryResponse
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/metrics/summary",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorEnvelope | MetricsSummaryResponse | None:
    if response.status_code == 200:
        response_200 = MetricsSummaryResponse.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = ErrorEnvelope.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorEnvelope.from_dict(response.json())

        return response_403

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorEnvelope | MetricsSummaryResponse]:
    return Response(
        status_code=response.status_code,
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[ErrorEnvelope | MetricsSummaryResponse]:
    """
    Get metrics summary

    Return low-cardinality counters, latency summaries, and activity rollups
    for dashboards.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.

    Returns:
        Response[ErrorEnvelope | MetricsSummaryResponse]: Detailed HTTP
            response wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
) -> ErrorEnvelope | MetricsSummaryResponse | None:
    """
    Get metrics summary

    Return low-cardinality counters, latency summaries, and activity rollups
    for dashboards.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.

    Returns:
        ErrorEnvelope | MetricsSummaryResponse | None: Parsed response
            payload, or ``None`` when unexpected statuses are ignored by the
            client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[ErrorEnvelope | MetricsSummaryResponse]:
    """
    Get metrics summary

    Return low-cardinality counters, latency summaries, and activity rollups
    for dashboards.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.

    Returns:
        Response[ErrorEnvelope | MetricsSummaryResponse]: Detailed HTTP
            response wrapper containing the parsed response payload.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
) -> ErrorEnvelope | MetricsSummaryResponse | None:
    """
    Get metrics summary

    Return low-cardinality counters, latency summaries, and activity rollups
    for dashboards.

    Args:
        client (AuthenticatedClient): SDK client used to send the request
            and parse the response.

    Returns:
        ErrorEnvelope | MetricsSummaryResponse | None: Parsed response
            payload, or ``None`` when unexpected statuses are ignored by the
            client.

    Raises:
        errors.UnexpectedStatus: If ``client.raise_on_unexpected_status`` is
            enabled and the API returns an undocumented status code.
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
