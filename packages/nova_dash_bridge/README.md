# nova-dash-bridge

Dash/browser helpers for integrating with the canonical Nova APIs.

This package ships two things only:

- `FileTransferAssets` for the packaged uploader JS/CSS bundle.
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
from nova_dash_bridge import FileTransferAssets, S3FileUploader

assets = FileTransferAssets()
uploader = S3FileUploader(
    "report-upload",
    max_bytes=25_000_000,
    allowed_extensions={".csv"},
    auth_header_element_id="nova-auth-header",
)
```

Install the Dash extra when you need the component surface:

```bash
pip install "nova-dash-bridge[dash]"
```
