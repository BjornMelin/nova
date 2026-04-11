# nova-workflows

Serverless workflow handlers for the canonical Nova export orchestration path
plus scheduled multipart reconciliation.

This package owns Step Functions task handlers, workflow runtime assembly,
local workflow task logic, and the scheduled reconciliation handler for expired
upload sessions and orphaned multipart uploads.

Workflow assembly consumes the canonical export-domain surface through
`nova_file_api.workflow_facade`. That includes the shared AWS client-config
helpers used by the workflow runtime so API and workflow paths keep the same
retry and timeout posture.

This package does not own API route wiring, FastAPI app assembly, or a second
runtime-authority seam.
