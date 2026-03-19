# Release and provisioning docs (index)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-19

## Purpose

Single table of contents for everything under `docs/plan/release/`. Use this
before scanning filenames. Operator narrative order is **core policy → runtime
infra → CI/CD → release execution → validation → governance → IAM/secrets →
troubleshooting → evidence**.

Canonical route/API authority for release work:
[release-authority-chain.md](release-authority-chain.md).

Parent routers: [`../PLAN.md`](../PLAN.md), [`../../runbooks/README.md`](../../runbooks/README.md),
[`../../architecture/README.md`](../../architecture/README.md).

## Core policy and artifacts

| Doc | Role |
| --- | --- |
| [RELEASE-POLICY.md](RELEASE-POLICY.md) | Branching, promotion, security, package rules |
| [RELEASE-RUNBOOK.md](RELEASE-RUNBOOK.md) | Plan/apply workflows, preconditions, execution |
| [RELEASE-VERSION-MANIFEST.md](RELEASE-VERSION-MANIFEST.md) | Selective versioning manifest (tooling path) |
| [runtime-config-contract.generated.md](runtime-config-contract.generated.md) | Generated ECS/env matrix from `Settings` |

## Provisioning sequence (recommended order)

1. [deploy-runtime-cloudformation-environments-guide.md](deploy-runtime-cloudformation-environments-guide.md) — `infra/runtime/**` for `dev` / `prod`
2. [day-0-operator-checklist.md](day-0-operator-checklist.md) — minimal first-time CI/CD path + `scripts/release/day-0-operator-command-pack.sh`
3. [docker-buildx-and-credential-helper-setup-guide.md](docker-buildx-and-credential-helper-setup-guide.md) — local image builds
4. [aws-oidc-and-iam-role-setup-guide.md](aws-oidc-and-iam-role-setup-guide.md), [aws-secrets-provisioning-guide.md](aws-secrets-provisioning-guide.md), [github-actions-secrets-and-vars-setup-guide.md](github-actions-secrets-and-vars-setup-guide.md), [codeconnections-activation-and-validation-guide.md](codeconnections-activation-and-validation-guide.md)
5. [deploy-nova-cicd-end-to-end-guide.md](deploy-nova-cicd-end-to-end-guide.md) — CI/CD stacks after runtime
6. [release-promotion-dev-to-prod-guide.md](release-promotion-dev-to-prod-guide.md) — immutable dev→prod promotion

## Operator reference

| Doc | Role |
| --- | --- |
| [config-values-reference-guide.md](config-values-reference-guide.md) | GitHub secrets/vars, command-pack keys, stack outputs |
| [runtime-config-contract.generated.md](runtime-config-contract.generated.md) | Env vars / overrides (regenerate via `generate_runtime_config_contract.py`) |

## Live validation

| Doc | Role |
| --- | --- |
| [NONPROD-LIVE-VALIDATION-RUNBOOK.md](NONPROD-LIVE-VALIDATION-RUNBOOK.md) | AWS-live gates: CodeConnections, ALB, cross-repo E2E, alarms, pipeline |
| [BROWSER-LIVE-VALIDATION-CHECKLIST.md](BROWSER-LIVE-VALIDATION-CHECKLIST.md) | Browser / `agent-browser` checklist for dash + Nova against real URLs |

Use **NONPROD** for infrastructure and pipeline integration; use **BROWSER**
for deterministic UI/route checks. They complement each other.

## Governance

| Doc | Role |
| --- | --- |
| [governance-lock-and-branch-protection.md](governance-lock-and-branch-protection.md) | Required checks, branch rules, `gh` verification |

## Specialized

| Doc | Role |
| --- | --- |
| [AUTH0-A0DEPLOY-RUNBOOK.md](AUTH0-A0DEPLOY-RUNBOOK.md) | Auth0 tenant ops + schema |
| [batch-b-access-unblock-guide.md](batch-b-access-unblock-guide.md) | Batch B IAM read path for validation |
| [troubleshooting-and-break-glass-guide.md](troubleshooting-and-break-glass-guide.md) | Failures and emergency commands |
| [HARD-CUTOVER-CHECKLIST.md](HARD-CUTOVER-CHECKLIST.md) | Stub → finalized checklist in history |

Release documentation style for this folder is covered under **Release operator
docs profile** in [`../../standards/repository-engineering-standards.md`](../../standards/repository-engineering-standards.md).

## Evidence

| Doc | Role |
| --- | --- |
| [evidence-log.md](evidence-log.md) | Append-only log of validation/promotion runs |
| [evidence/README.md](evidence/README.md) | How to add evidence artifacts |
