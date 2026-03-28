# Client and downstream integration docs

Status: Active
Current repository state: **pre-wave-2 implementation baseline**
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

That file supersedes the older split file/auth SDK posture as the implementation
target, but the current repository may still carry the older packages until the
branch program lands.

## Rule

Do not confuse current downstream workflow examples with the future canonical
SDK package layout.
