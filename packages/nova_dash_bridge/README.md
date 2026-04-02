# nova-dash-bridge

Dash/browser helpers for integrating with the canonical Nova APIs.

This package ships three browser-only helpers:

- `FileTransferAssets` for the packaged uploader JS/CSS bundle.
- `BearerAuthHeader` for the hidden DOM node that carries the explicit bearer
  header contract.
- `S3FileUploader` for the Dash component shell that drives that browser
  runtime.

It does not embed Nova into FastAPI or Flask hosts, and it does not expose an
in-process transfer service seam. Server-side integrations should call the
canonical Nova HTTP API instead of mounting bridge-owned route adapters.

Canonical browser endpoint alignment:

- Transfer routes: `/v1/transfers/*`
- Export routes: `/v1/exports/*`
- Legacy `/api/*` and `/v1/jobs*` route families are not part of the runtime
  contract.

Minimal usage:

```python
from nova_dash_bridge import BearerAuthHeader, FileTransferAssets, S3FileUploader

assets = FileTransferAssets()
auth_header = BearerAuthHeader(
    auth_header_element_id="nova-auth-header",
    authorization_header="Bearer <token>",
)
uploader = S3FileUploader(
    "report-upload",
    max_bytes=25_000_000,
    allowed_extensions={".csv"},
    auth_header_element_id="nova-auth-header",
)
```

`FileTransferAssets()` is self-contained by default. It emits `data:` URLs for
the packaged JavaScript and CSS so a Dash app does not need a deleted Flask
asset registrar or another host-specific asset mount. If a deployment uses a
strict CSP that disallows `data:` script/style sources, pass an explicit
`assets_url_prefix` and serve `/file_transfer.js` and `/file_transfer.css`
there instead.

`BearerAuthHeader()` does not fetch or refresh tokens. The consumer app remains
responsible for obtaining the current bearer token and rendering the full
`Authorization` header value into the hidden node. The uploader JavaScript reads
that node and sends `Authorization` with `credentials: "omit"`.

Install the Dash extra when you need the component surface:

```bash
pip install "nova-dash-bridge[dash]"
```
