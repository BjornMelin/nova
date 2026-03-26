# nova-dash-bridge

Dash, FastAPI, and Flask bridge adapters for integrating with Nova APIs.

Runtime shape:

- `nova_file_api.public` is the canonical in-process transfer contract.
- FastAPI integrations await the async bridge/public surface directly.
- Flask and Dash keep an explicit thin sync adapter for sync-only hosts.
- Bridge packages do not own alternate transfer models, route authority, or
  bridge-local threadpool tuning config for FastAPI.
- `create_fastapi_router()` is route composition only; shared request-context
  and exception-registration behavior comes from `nova_runtime_support`.
- FastAPI integrations require async auth resolution and an async-capable S3
  factory path; sync-only auth and sync-only S3 factories belong only on the
  explicit sync adapter surface.

Canonical adapter endpoint alignment:

- Transfer routes: `/v1/transfers/*`
- Export routes: `/v1/exports/*`
- Legacy `/api/*` route families are not part of the runtime contract.

Minimal usage:

```python
from nova_dash_bridge import create_fastapi_router

router = create_fastapi_router(
    env_config=env_config,
    upload_policy=upload_policy,
    auth_policy=auth_policy,
)
```

The FastAPI path stays async end to end. If you are integrating with a true
sync host such as Flask, use the explicit sync bridge helpers instead of
wrapping the async surface back through threadpools.
