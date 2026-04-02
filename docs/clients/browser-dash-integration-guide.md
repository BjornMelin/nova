# Browser and Dash Integration Guide

Status: Active
Last reviewed: 2026-04-01

This guide is the canonical downstream path for using
`packages/nova_dash_bridge` in a Dash app after the browser-only hard cut.

## What the bridge owns

`nova_dash_bridge` owns only three browser-side helpers:

- `FileTransferAssets()` injects the packaged uploader JavaScript and CSS.
- `BearerAuthHeader()` renders the hidden DOM node that carries the explicit
  bearer header contract.
- `S3FileUploader(...)` renders the Dash component shell that the packaged
  JavaScript attaches to.

The bridge does not own:

- token acquisition
- token refresh
- server-side auth resolution
- Flask or FastAPI asset registration
- cookie-based auth transport

## Canonical integration pattern

Mount the assets once near the top of the Dash layout:

```python
from dash import html
from nova_dash_bridge import FileTransferAssets

layout = html.Div(
    [
        FileTransferAssets(),
        html.Main(id="app-content"),
    ]
)
```

Render the current bearer header into a hidden DOM node:

```python
from nova_dash_bridge import BearerAuthHeader

auth_header = BearerAuthHeader(
    auth_header_element_id="nova-auth-header",
    authorization_header=f"Bearer {token}",
)
```

Pass that node id into the uploader:

```python
from nova_dash_bridge import S3FileUploader

uploader = S3FileUploader(
    "report-upload",
    max_bytes=25_000_000,
    allowed_extensions={".csv", ".xlsx"},
    transfers_endpoint_base="/v1/transfers",
    exports_endpoint_base="/v1/exports",
    auth_header_element_id="nova-auth-header",
    async_exports_enabled=True,
    async_export_min_bytes=10_000_000,
)
```

Compose them in one place:

```python
from dash import html
from nova_dash_bridge import BearerAuthHeader, FileTransferAssets, S3FileUploader

layout = html.Div(
    [
        FileTransferAssets(),
        BearerAuthHeader(
            auth_header_element_id="nova-auth-header",
            authorization_header=f"Bearer {token}",
        ),
        S3FileUploader(
            "report-upload",
            max_bytes=25_000_000,
            allowed_extensions={".csv"},
            transfers_endpoint_base="/v1/transfers",
            exports_endpoint_base="/v1/exports",
            auth_header_element_id="nova-auth-header",
        ),
    ]
)
```

## Asset delivery contract

`FileTransferAssets()` is self-contained by default. It emits `data:` URLs for
the packaged CSS and JavaScript so the consumer app does not need a deleted
Flask asset registrar or another bridge-specific asset mount.

Use `assets_url_prefix` only when a deployment has a strict CSP that disallows
`data:` script/style sources:

```python
FileTransferAssets(assets_url_prefix="/assets/nova_dash_bridge")
```

When you opt into external delivery, the host app must serve:

- `/assets/nova_dash_bridge/file_transfer.css`
- `/assets/nova_dash_bridge/file_transfer.js`

Do not recreate the deleted Flask/FastAPI bridge adapters just to serve these
files.

## Auth contract

The browser contract is explicit:

- the hidden DOM node must contain the full `Authorization` header value
- the uploader JavaScript reads that node on each request
- browser requests send `Authorization`
- browser requests keep `credentials: "omit"`

Do not switch this flow to cookies, same-origin session headers, or bridge-owned
token resolution.

If a downstream app prefers not to use `BearerAuthHeader()`, the raw DOM shape
is still simple:

```python
from dash import html

html.Div(
    f"Bearer {token}",
    id="nova-auth-header",
    hidden=True,
    style={"display": "none"},
    **{"aria-hidden": "true"},
)
```

## Operational notes

- Canonical transfer endpoints live under `/v1/transfers`.
- Canonical export endpoints live under `/v1/exports`.
- Legacy `/api/*` and `/v1/jobs*` paths are retired.
- Token acquisition still belongs to the consumer app.
- The bridge payload remains browser-only and does not introduce host adapter
  semantics back into Nova.
