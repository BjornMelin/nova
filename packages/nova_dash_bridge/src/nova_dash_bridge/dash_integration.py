"""Dash helpers for uploader assets and UI integration."""

from __future__ import annotations

from base64 import b64encode
from functools import cache
from importlib import resources
from typing import Any, cast

from dash import dcc, html


@cache
def _asset_text(name: str) -> str:
    """Return packaged asset text for inline delivery.

    Raises:
        RuntimeError: If the packaged asset cannot be read.
    """
    try:
        return (
            resources.files("nova_dash_bridge.assets")
            .joinpath(name)
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise RuntimeError(
            "Unable to load packaged nova_dash_bridge asset "
            f"{name!r} for inline delivery. Pass assets_url_prefix to "
            "FileTransferAssets() and serve the packaged files externally "
            "if inline assets are unavailable in this environment."
        ) from exc


@cache
def _asset_data_url(name: str, mime_type: str) -> str:
    """Return a data URL for a packaged asset."""
    encoded_asset = b64encode(_asset_text(name).encode("utf-8")).decode("ascii")
    return f"data:{mime_type};base64,{encoded_asset}"


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
    assets_url_prefix: str | None = None,
) -> html.Div:
    """Return package-managed uploader assets for Dash layouts.

    When ``assets_url_prefix`` is omitted, the helper uses self-contained data
    URLs so the consumer app does not need a host-side asset registrar. Pass an
    explicit prefix only when a deployment needs separately hosted assets, such
    as a strict CSP that disallows ``data:`` script/style sources.
    """
    if assets_url_prefix is None:
        script_src = _asset_data_url(
            "file_transfer.js",
            "text/javascript",
        )
        css_href = _asset_data_url(
            "file_transfer.css",
            "text/css",
        )
    else:
        normalized_prefix = assets_url_prefix.rstrip("/")
        script_src = f"{normalized_prefix}/file_transfer.js"
        css_href = f"{normalized_prefix}/file_transfer.css"

    return html.Div(
        [
            html.Link(rel="stylesheet", href=css_href),
            html.Script(src=script_src),
        ]
    )


def BearerAuthHeader(
    *,
    auth_header_element_id: str,
    authorization_header: str | None = None,
) -> html.Div:
    """Render the hidden DOM node read by the uploader's bearer contract."""
    element_id = auth_header_element_id.strip()
    if not element_id:
        raise ValueError("auth_header_element_id must not be blank")

    return html.Div(
        authorization_header or "",
        id=element_id,
        hidden=True,
        style={"display": "none"},
        **cast(dict[str, Any], {"aria-hidden": "true"}),
    )


def S3FileUploader(
    component_id: str,
    *,
    max_bytes: int,
    allowed_extensions: set[str],
    multiple: bool = False,
    transfers_endpoint_base: str = "/v1/transfers",
    exports_endpoint_base: str = "/v1/exports",
    auth_header_element_id: str = "",
    max_concurrency: int = 4,
    sign_batch_size: int | None = None,
    async_exports_enabled: bool = False,
    async_export_min_bytes: int = 0,
    async_export_poll_interval_ms: int = 2000,
    async_export_timeout_ms: int = 900000,
) -> html.Div:
    """Render a Dash uploader shell driven by package JavaScript.

    Args:
        component_id: Dash component id.
        max_bytes: Maximum upload size accepted by UI validation.
        allowed_extensions: Allowed upload extensions.
        multiple: Whether multiple file uploads are allowed.
        transfers_endpoint_base: Base path for transfer endpoints.
        exports_endpoint_base: Base path for async export endpoints.
        auth_header_element_id: DOM element id containing the full
            ``Authorization`` header value (for example ``Bearer <token>``).
        max_concurrency: Multipart upload worker concurrency.
        sign_batch_size: Optional multipart sign batch size override.
        async_exports_enabled: Toggle async export workflow initiation.
        async_export_min_bytes: Minimum size to use async flow.
        async_export_poll_interval_ms: Poll interval for async export status.
        async_export_timeout_ms: Poll timeout for async export completion.

    Returns:
        html.Div: Upload component shell for browser-side runtime.
    """
    accepted = _normalize_allowed_extensions(allowed_extensions)
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
        value=async_export_min_bytes,
        field_name="async_export_min_bytes",
    )
    poll_interval_ms = _validate_positive(
        value=async_export_poll_interval_ms,
        field_name="async_export_poll_interval_ms",
    )
    timeout_ms = _validate_positive(
        value=async_export_timeout_ms,
        field_name="async_export_timeout_ms",
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
                "data-exports-endpoint-base": exports_endpoint_base,
                "data-auth-header-element-id": auth_header_element_id,
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
                "data-async-exports-enabled": str(
                    async_exports_enabled
                ).lower(),
                "data-async-export-min-bytes": str(min_bytes),
                "data-async-export-poll-interval-ms": str(poll_interval_ms),
                "data-async-export-timeout-ms": str(timeout_ms),
            },
        ),
    )
