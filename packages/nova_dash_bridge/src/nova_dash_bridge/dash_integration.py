"""Dash helpers for uploader assets and UI integration."""

from __future__ import annotations

from typing import Any, cast

from dash import dcc, html


def _normalize_allowed_extensions(allowed_extensions: set[str]) -> set[str]:
    """Return normalized extension values for browser accept filters.

    Args:
        allowed_extensions: Raw extension values from caller configuration.

    Returns:
        set[str]: Normalized lowercase extensions prefixed with ``.``.

    Raises:
        TypeError: If entries are not strings.
        ValueError: If entries are blank or normalize to an empty set.
    """
    normalized: set[str] = set()
    for raw_value in allowed_extensions:
        if not isinstance(raw_value, str):
            raise TypeError(
                "allowed_extensions entries must be non-empty strings"
            )
        raw = raw_value.strip().lower()
        if not raw:
            raise ValueError(
                "allowed_extensions entries must be non-empty strings"
            )
        normalized.add(raw if raw.startswith(".") else f".{raw}")
    if not normalized:
        raise ValueError("allowed_extensions must not be empty")
    return normalized


def _normalize_async_job_type(async_job_type: str) -> str:
    """Return a non-empty async job type string."""
    value = async_job_type.strip()
    if not value:
        raise ValueError("async_job_type must be a non-empty string")
    return value


def _validate_non_negative(
    *,
    value: int,
    field_name: str,
) -> int:
    """Validate an integer config field is non-negative."""
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return value


def _validate_positive(
    *,
    value: int,
    field_name: str,
) -> int:
    """Validate an integer config field is strictly positive."""
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return value


def FileTransferAssets(
    *,
    assets_url_prefix: str = "/_assets/nova_dash_bridge",
) -> html.Div:
    """Return script/link tags for package-managed uploader assets."""
    script_src = f"{assets_url_prefix}/file_transfer.js"
    css_href = f"{assets_url_prefix}/file_transfer.css"
    return html.Div(
        [
            html.Link(rel="stylesheet", href=css_href),
            html.Script(src=script_src),
        ]
    )


def S3FileUploader(
    component_id: str,
    *,
    max_bytes: int,
    allowed_extensions: set[str],
    multiple: bool = False,
    transfers_endpoint_base: str = "/v1/transfers",
    jobs_endpoint_base: str = "/v1/jobs",
    max_concurrency: int = 4,
    sign_batch_size: int | None = None,
    async_jobs_enabled: bool = False,
    async_job_type: str = "process_upload",
    async_job_min_bytes: int = 0,
    async_job_poll_interval_ms: int = 2000,
    async_job_timeout_ms: int = 900000,
) -> html.Div:
    """Render a Dash uploader shell driven by package JavaScript.

    Args:
        component_id: Dash component id.
        max_bytes: Maximum upload size accepted by UI validation.
        allowed_extensions: Allowed upload extensions.
        multiple: Whether multiple file uploads are allowed.
        transfers_endpoint_base: Base path for transfer endpoints.
        jobs_endpoint_base: Base path for async job endpoints.
        max_concurrency: Multipart upload worker concurrency.
        sign_batch_size: Optional multipart sign batch size override.
        async_jobs_enabled: Toggle async background job flow.
        async_job_type: Job type name for enqueue requests.
        async_job_min_bytes: Minimum size to use async flow.
        async_job_poll_interval_ms: Poll interval for async job status.
        async_job_timeout_ms: Poll timeout for async job completion.

    Returns:
        html.Div: Upload component shell for browser-side runtime.
    """
    accepted = _normalize_allowed_extensions(allowed_extensions)
    normalized_job_type = _normalize_async_job_type(async_job_type)
    max_bytes = _validate_positive(value=max_bytes, field_name="max_bytes")
    max_concurrency = _validate_positive(
        value=max_concurrency,
        field_name="max_concurrency",
    )
    if sign_batch_size is not None:
        sign_batch_size = _validate_positive(
            value=sign_batch_size,
            field_name="sign_batch_size",
        )
        sign_batch_cap = min(16, max_concurrency * 2)
        if sign_batch_size > sign_batch_cap:
            raise ValueError(
                "sign_batch_size must be less than or equal to "
                f"min(16, 2 * max_concurrency) ({sign_batch_cap})"
            )
    min_bytes = _validate_non_negative(
        value=async_job_min_bytes,
        field_name="async_job_min_bytes",
    )
    poll_interval_ms = _validate_positive(
        value=async_job_poll_interval_ms,
        field_name="async_job_poll_interval_ms",
    )
    timeout_ms = _validate_positive(
        value=async_job_timeout_ms,
        field_name="async_job_timeout_ms",
    )
    accept_value = ",".join(sorted(accepted))
    return html.Div(
        [
            dcc.Store(id=f"{component_id}-result", storage_type="memory"),
            dcc.Store(id=f"{component_id}-progress", storage_type="memory"),
            html.Div(
                id=f"{component_id}-dropzone",
                className="nova-dropzone",
                tabIndex=0,
                children=[
                    html.Div("Drag & drop file here, or click to choose"),
                    html.Div(
                        f"Allowed: {accept_value} | Max: {max_bytes} bytes",
                        className="nova-caption",
                    ),
                ],
            ),
        ],
        id=component_id,
        className="nova-uploader",
        **cast(
            dict[str, Any],
            {
                "data-transfers-endpoint-base": transfers_endpoint_base,
                "data-jobs-endpoint-base": jobs_endpoint_base,
                "data-dropzone-id": f"{component_id}-dropzone",
                "data-input-id": f"{component_id}-input",
                "data-result-store-id": f"{component_id}-result",
                "data-progress-store-id": f"{component_id}-progress",
                "data-max-concurrency": str(max_concurrency),
                "data-sign-batch-size": (
                    "" if sign_batch_size is None else str(sign_batch_size)
                ),
                "data-resume-namespace": component_id,
                "data-max-bytes": str(max_bytes),
                "data-accept": accept_value,
                "data-multiple": str(multiple).lower(),
                "data-async-jobs-enabled": str(async_jobs_enabled).lower(),
                "data-async-job-type": normalized_job_type,
                "data-async-job-min-bytes": str(min_bytes),
                "data-async-job-poll-interval-ms": str(poll_interval_ms),
                "data-async-job-timeout-ms": str(timeout_ms),
            },
        ),
    )
