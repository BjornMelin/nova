# nova-dash-bridge

Dash, FastAPI, and Flask bridge adapters for integrating with Nova APIs.

Canonical adapter endpoint alignment:

- Transfer routes: `/v1/transfers/*`
- Job routes: `/v1/jobs/*`
- Legacy `/api/*` route families are not part of the runtime contract.
