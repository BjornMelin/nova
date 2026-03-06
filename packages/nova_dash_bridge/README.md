# nova-dash-bridge

Dash, FastAPI, and Flask bridge adapters for integrating with Nova APIs.

Canonical adapter endpoint alignment:

- Transfer routes: `/v1/transfers/*`
- Job routes: `/v1/jobs/*`
- Legacy `/api/*` route families are not part of the runtime contract.
- Default async enqueue job type is `transfer.process`.
- Successful async transfer completions return `result.export_key` and
  `result.download_filename` for follow-up download presign flows.
