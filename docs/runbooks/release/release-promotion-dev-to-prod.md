# Release Promotion Dev-to-Prod Addendum

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-24

## Purpose

This guide is a narrow addendum for the Dev to Prod promotion step only.
Canonical release execution, evidence capture, and durable record policy remain
owned by `release-runbook.md` and `release-policy.md`.

## Scope

- Use this guide after staged publish and Dev validation have already completed.
- Do not use this file as the primary release runbook.
- For immutable artifact and package-evidence requirements, defer to
  `release-runbook.md`.

## Inputs

- `${AWS_REGION}`
- `${CODEPIPELINE_NAME}`
- `${PIPELINE_EXECUTION_ID}`
- `${MANIFEST_SHA256}`
- `${CHANGED_UNITS_JSON}`
- `${VERSION_PLAN_JSON}`
- `${PROMOTION_CANDIDATES_JSON}`

## Promotion Procedure

1. Confirm the latest pipeline execution and capture the execution ID.
2. Confirm `DeployDev` and `ValidateDev` have succeeded before prod promotion.
3. Dispatch `Promote Prod` with:
   - `manifest_sha256` from `codeartifact-gate-report.json`
   - `changed_units_json` from `changed-units.json`
   - `version_plan_json` from `version-plan.json`
   - `promotion_candidates_json` from
     `codeartifact-promotion-candidates.json`
4. Confirm package promotion copies from
   `CODEARTIFACT_STAGING_REPOSITORY` to `CODEARTIFACT_PROD_REPOSITORY`.
5. Confirm `DeployProd` and `ValidateProd` complete successfully.

## Promotion-Specific Acceptance Checks

- The promoted artifact set is sourced from the already gate-validated staged
  publish outputs.
- `FILE_IMAGE_DIGEST` continuity is preserved from Dev to Prod.
- No rebuild occurs between Dev and Prod.
- Manual approval identity and timestamp are preserved in the workflow/pipeline
  record.

## Evidence Boundary

Use `release-runbook.md` for the authoritative evidence checklist and
`release-policy.md` for durable-pointer policy. This file adds no separate
evidence requirements beyond the promotion-specific checks above.

## References

- `release-runbook.md`
- `release-policy.md`
- `nonprod-live-validation-runbook.md`
- CodePipeline manual approvals:
  <https://docs.aws.amazon.com/codepipeline/latest/userguide/approvals-action-add.html>
- CodePipeline list-action-executions API:
  <https://docs.aws.amazon.com/cli/latest/reference/codepipeline/list-action-executions.html>
