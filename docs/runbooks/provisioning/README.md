# Provisioning runbooks (index)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-24

## Purpose

First-time and ongoing **AWS / GitHub / local workstation** setup for Nova
release and CI/CD. Execute in roughly this order; then use
[`../release/README.md`](../release/README.md) for release and validation.

Before running day-0 or end-to-end flows, read:

- [config-values-reference.md](config-values-reference.md)
- [github-actions-secrets-and-vars.md](github-actions-secrets-and-vars.md)

## Recommended order

1. [deploy-runtime-cloudformation-environments.md](deploy-runtime-cloudformation-environments.md) -- `infra/runtime/**` for `dev` / `prod`
2. [day-0-operator-checklist.md](day-0-operator-checklist.md) -- minimal CI/CD path + `scripts/release/day-0-operator-command-pack.sh`
3. [docker-buildx-credential-helper-setup.md](docker-buildx-credential-helper-setup.md) -- local Docker BuildKit / credential helper
4. [aws-oidc-and-iam-role-setup.md](aws-oidc-and-iam-role-setup.md), [aws-secrets-provisioning.md](aws-secrets-provisioning.md), [github-actions-secrets-and-vars.md](github-actions-secrets-and-vars.md), [codeconnections-activation-and-validation.md](codeconnections-activation-and-validation.md)
5. [nova-cicd-end-to-end-deploy.md](nova-cicd-end-to-end-deploy.md) -- CI/CD stacks after runtime

## Reference

| Doc | Role |
| --- | --- |
| [config-values-reference.md](config-values-reference.md) | GitHub secrets/vars, command-pack keys, stack outputs |
| [github-actions-secrets-and-vars.md](github-actions-secrets-and-vars.md) | Canonical GitHub repository secret/variable setup for Nova release automation |

Route/API documentation authority:
[`../release/README.md#canonical-documentation-authority-chain`](../release/README.md#canonical-documentation-authority-chain).

Generated runtime env matrix ([`docs/release/runtime-config-contract.generated.md`](../../release/runtime-config-contract.generated.md)).
