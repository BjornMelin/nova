# Engineering standards

Status: Active
Current repository state: **canonical serverless baseline**
Last reviewed: 2026-04-10

## Purpose

Route readers to the engineering workflow standards that govern the active repo
surface.

## Read after `AGENTS.md`

1. `../../AGENTS.md`
2. `../README.md`
3. `../architecture/README.md`
4. `./repository-engineering-standards.md`

## Active standards

- `repository-engineering-standards.md`
- current CI/workflow files in `.github/workflows/`
- current release and provisioning runbooks

## Authority / references

- `../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `../architecture/spec/SPEC-0027-public-api-v2.md`
- `../architecture/requirements.md`
- `../runbooks/release/release-runbook.md`

## Rule

Keep standards aligned to the active package graph, the surviving GitHub
workflow surface, and `infra/nova_cdk`. Do not preserve deleted deploy-runtime
or release-control-plane assumptions in active verification commands from the
legacy ECS/CloudFormation-era deploy-runtime or release-control-plane surfaces.
