# Client and downstream integration docs

Status: Active
Current repository state: **mixed wave-2 implementation baseline**
Last reviewed: 2026-03-25

## Current baseline consumer docs

These remain useful for the current repository shape and downstream workflow
integration:

- `post-deploy-validation-integration-guide.md`
- `dash-minimal-workflow.yml`
- `rshiny-minimal-workflow.yml`
- `react-next-minimal-workflow.yml`
- `examples/workflows/*`

## Approved target-state client/package plan

For the canonical package map that implementation agents should follow, use:

- `CLIENT-SDK-CANONICAL-PACKAGES.md`

That file reflects the canonical package map already landed in the current repo;
client examples and downstream workflow docs should continue to align to those
packages rather than the older split file/auth SDK posture.

## Rule

Do not confuse current downstream workflow examples with retired split-package
assumptions. The canonical SDK package layout is now the active baseline.
