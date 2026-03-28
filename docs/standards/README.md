# Engineering standards

Status: Active
Current repository state: **canonical wave-2 serverless baseline**
Last reviewed: 2026-03-28

## Purpose

Route readers to the engineering workflow standards that govern the active repo
surface.

## Read after `AGENTS.md`

1. `../../AGENTS.md`
2. `../README.md`
3. `../architecture/README.md`
4. `./repository-engineering-standards.md`
5. `./DECISION-FRAMEWORKS-GREENFIELD-2026.md`

## Active standards

- `repository-engineering-standards.md`
- current CI/workflow files in `.github/workflows/`
- current release and provisioning runbooks

## Rule

Keep standards aligned to the active package graph, the surviving GitHub
workflow surface, and `infra/nova_cdk`. Do not preserve deleted deploy-runtime
or release-control-plane assumptions in active verification commands.
