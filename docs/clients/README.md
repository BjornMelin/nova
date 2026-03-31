# Client and downstream integration docs

Status: Active
Current repository state: **canonical wave-2 serverless baseline**
Last reviewed: 2026-03-28

## Active client docs

- `CLIENT-SDK-CANONICAL-PACKAGES.md`
- `post-deploy-validation-integration-guide.md`
- `dash-minimal-workflow.yml`
- `rshiny-minimal-workflow.yml`
- `react-next-minimal-workflow.yml`
- `examples/workflows/*`

## Authority / references

- `../overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `../architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `../architecture/adr/ADR-0038-docs-authority-reset.md`
- `../architecture/spec/SPEC-0027-public-api-v2.md`
- `../architecture/spec/SPEC-0029-platform-serverless.md`
- `../architecture/spec/SPEC-0030-sdk-generation-and-package-layout.md`
- `../contracts/deploy-output-authority-v2.schema.json`
- `../contracts/workflow-post-deploy-validate.schema.json`
- `../runbooks/release/release-runbook.md`

## Rule

Downstream examples must target the unified SDK packages and the surviving
reusable post-deploy validation workflow only.
When downstream automation needs the runtime base URL, it must derive that
authority from Nova `deploy-output.json` rather than a manually entered
`NOVA_API_BASE_URL`.
