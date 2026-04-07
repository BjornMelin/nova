# nova-workflows

Serverless workflow handlers for the canonical Nova export orchestration path.

This package owns Step Functions task handlers, workflow runtime assembly, and
local workflow task logic.

Workflow assembly consumes the canonical export-domain surface through
`nova_file_api.workflow_facade`. That includes the shared AWS client-config
helpers used by the workflow runtime so API and workflow paths keep the same
retry and timeout posture.

This package does not own API route wiring, FastAPI app assembly, or a second
runtime-authority seam.
