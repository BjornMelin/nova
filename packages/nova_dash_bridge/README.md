# nova-dash-bridge

Dash, FastAPI, and Flask bridge adapters for integrating with Nova APIs.

Runtime shape:

- `nova_file_api.public` is the canonical in-process transfer contract.
- FastAPI integrations use the async bridge surface directly.
- Flask and Dash keep an explicit thin sync adapter for sync-only hosts.
- Bridge packages do not own alternate transfer models, route authority, or
  bridge-local threadpool tuning config for FastAPI.

Canonical adapter endpoint alignment:

- Transfer routes: `/v1/transfers/*`
- Job routes: `/v1/jobs/*`
- Legacy `/api/*` route families are not part of the runtime contract.
