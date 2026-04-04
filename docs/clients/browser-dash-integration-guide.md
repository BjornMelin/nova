# Browser and Dash Integration Guide

Status: Active
Owner: nova client surface
Last reviewed: 2026-04-02

This guide is the canonical downstream path for using
`packages/nova_dash_bridge` in a Dash app after the browser-only hard cut.

## Audience and outcome

Use this guide when a junior team needs one clear path from Nova deployment
evidence to a working Dash uploader. By the end, you should have:

- the canonical Nova runtime URL from `deploy-output.json`
- a Dash layout that mounts Nova uploader assets once
- an explicit bearer-header node that the browser runtime can read
- an `S3FileUploader(…)` wired to the live transfers and exports routes
- a clear choice for any server-side SDK calls that your app still needs

## What Nova owns vs what your app owns

Nova owns:

- the HTTPS runtime authority in `deploy-output.json.public_base_url`
- the transfer API under `/v1/transfers/*`
- the export API under `/v1/exports*`
- the effective transfer policy surface under `/v1/capabilities/transfers`
- the packaged browser helpers in `nova_dash_bridge`

Your app owns:

- acquiring and refreshing bearer tokens
- rendering the full `Authorization` header into the hidden DOM node
- choosing whether to call Nova directly from the browser or via your own
  server-side SDK usage
- ensuring the Dash origin is allowed by Nova CORS

## Step 1: read the deployed runtime authority

Do not hard-code the Nova base URL in a runbook or onboarding doc. Read it from
the authoritative deploy artifact wherever you store it (for example a release
download, CI artifact path, or your app repository root if you copy it there):

```bash
jq -r '.public_base_url' /path/to/deploy-output.json
```

The field you want is `public_base_url`. `execute_api_endpoint` is emitted for
validation and troubleshooting, not as the intended public ingress.

While you are reading the artifact, also confirm:

- `cors_allowed_origins` includes the Dash origin you will serve from
- `environment` and `runtime_version` match the deployment you intend to use

## Step 2: choose the right client surface

Use `nova_dash_bridge` only for browser upload/download behavior inside Dash.
Use an SDK or plain HTTP client when you need server-side Nova calls.

- Dash/browser uploads: `pip install "nova-dash-bridge[dash]"`
- Python server-side calls: `pip install nova-sdk-py`
- TypeScript server-side calls: `@nova/sdk`
- R consumers: package `nova`

## Step 3: keep the runtime URL in app config

Normalize the deploy-output value once and build the route bases from it:

```python
nova_base_url = "https://nova.example.com".rstrip("/")
transfers_endpoint_base = f"{nova_base_url}/v1/transfers"
exports_endpoint_base = f"{nova_base_url}/v1/exports"
```

This is the safest default for a Dash app that talks directly to Nova.

## Step 4: mount the packaged assets once

Render `FileTransferAssets()` near the top of the Dash layout:

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

`FileTransferAssets()` is self-contained by default. It emits `data:` URLs for
the packaged CSS and JavaScript, so a consumer app does not need a separate
host-specific asset registration layer.

If your deployment enforces a strict CSP that blocks `data:` script/style
sources, pass `assets_url_prefix` and serve the packaged files there:

```python
FileTransferAssets(assets_url_prefix="/assets/nova_dash_bridge")
```

That external path must serve:

- `/assets/nova_dash_bridge/file_transfer.css`
- `/assets/nova_dash_bridge/file_transfer.js`

## Step 5: render the bearer-header node

The browser runtime reads the full `Authorization` header from a hidden DOM
node. Consumer apps stay responsible for producing that value.

```python
from nova_dash_bridge import BearerAuthHeader

auth_header = BearerAuthHeader(
    auth_header_element_id="nova-auth-header",
    authorization_header=f"Bearer {token}",
)
```

The contract is simple:

- the element id must match what `S3FileUploader(…)` receives
- the text content must be the full header value, usually `Bearer <token>`
- browser requests keep `credentials: "omit"`

## Step 6: mount the uploader

```python
from nova_dash_bridge import S3FileUploader

uploader = S3FileUploader(
    "report-upload",
    max_bytes=25_000_000,
    allowed_extensions={".csv", ".xlsx"},
    transfers_endpoint_base=transfers_endpoint_base,
    exports_endpoint_base=exports_endpoint_base,
    auth_header_element_id="nova-auth-header",
    async_exports_enabled=True,
    async_export_min_bytes=10_000_000,
)
```

Key props:

- `transfers_endpoint_base`: usually `f"{public_base_url}/v1/transfers"`
- `exports_endpoint_base`: usually `f"{public_base_url}/v1/exports"`
- `auth_header_element_id`: the hidden bearer-header node id
- `async_exports_enabled`: turn on export creation/polling after upload
- `async_export_min_bytes`: optional threshold for large-file export flows
- `workload_class`: optional transfer policy selector for the current uploader
- `policy_hint`: optional transfer policy profile selector
- `checksum_preference`: optional checksum preference (`none`, `standard`, or
  `strict`)

The browser helper also consumes additive initiate response hints from Nova:

- `part_size_bytes`
- `max_concurrency_hint`
- `sign_batch_size_hint`
- `session_id`
- `resumable_until`
- `accelerate_enabled`
- `checksum_algorithm`
- `checksum_mode`

These values let Nova tune multipart behavior without forcing consumer apps to
ship hard-coded large-file thresholds.

Clients that preflight the transfer policy surface should also treat
`active_multipart_upload_limit`, `daily_ingress_budget_bytes`, and
`sign_requests_per_upload_limit` as the effective quota envelope for the
current deployed environment. The same capability response also exposes:

- `accelerate_enabled` for policy-scoped Transfer Acceleration
- `checksum_algorithm` and `checksum_mode` for checksum posture
- `large_export_worker_threshold_bytes` for the export worker-lane switch point

## Step 7: compose the layout in one place

```python
from dash import html
from nova_dash_bridge import BearerAuthHeader, FileTransferAssets, S3FileUploader

nova_base_url = "https://nova.example.com".rstrip("/")

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
            transfers_endpoint_base=f"{nova_base_url}/v1/transfers",
            exports_endpoint_base=f"{nova_base_url}/v1/exports",
            auth_header_element_id="nova-auth-header",
            workload_class="interactive",
            checksum_preference="standard",
        ),
    ]
)
```

## Step 8: read the uploader result payload

`S3FileUploader(…)` writes its result into the Dash memory store that matches
the component id. The base upload result contains:

- `bucket`
- `key`
- `filename`
- `size_bytes`
- `content_type`

When async exports are enabled and used, the result also includes:

- `export_id`
- `export_status`
- `export_output`
- `download`

That gives a Dash callback enough information to persist the upload reference,
start downstream processing, or hand a completed export download URL to the
user.

## Step 9: use SDKs only where they help

The bridge is not a replacement for the SDKs.

- Use `nova-sdk-py` when your Dash server needs to call Nova outside the
  browser uploader flow.
- Use `@nova/sdk` for TypeScript services or tools.
- Use R package `nova` for R-side service integrations.

All SDKs should use the same `public_base_url` authority that came from
`deploy-output.json`.

## Operational notes

- Keep token acquisition and refresh in the consumer app.
- Keep the browser flow bearer-only; do not switch to cookie transport.
- Treat `public_base_url` as the public ingress and `execute_api_endpoint` as
  validation evidence only.
- Let Nova-supplied concurrency, part-size, acceleration, and checksum hints
  drive the browser uploader unless you have a measured reason to tighten them
  further in the consumer app.
- Use `docs/clients/post-deploy-validation-integration-guide.md` when you also
  want automated downstream runtime validation.
