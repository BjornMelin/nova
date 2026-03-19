# Hard-Cutover Checklist (archived)

Status: Finalized (historical)
Owner: Release Architecture
Archived from: `docs/plan/release/HARD-CUTOVER-CHECKLIST.md` (2026-03-19)

This file is retained for audit. It is **not** active operator authority. For
current release docs, use [`docs/plan/release/README.md`](../../../plan/release/README.md).

---

## Hard-Cutover Checklist

Status: Finalized
Owner: Release Architecture

## 1. Runtime Contract Cutover

- [x] Canonical consumer capability endpoints use `/v1/*` routes.
- [x] Runtime route surface is limited to canonical `/v1/*` plus `/metrics/summary`.
- [x] Non-canonical route literals are absent from runtime handlers and public
  contract/docs authority surfaces.
- [x] Deploy-validation buildspecs/workflows may include explicit legacy route
  probes for required `404` checks.
- [x] No deprecated alias route namespace remains in runtime code.
- [x] OpenAPI regression test enforces canonical route contract only.
- [x] CI route guard includes regex route-literal checks for canonical paths
  (including `/v1/jobs/{id}/events`).
- [x] Generated OpenAPI client smoke test passes.
- [x] Workspace package/app metadata uses in-project `README.md` paths and
  isolated package builds succeed.

## 2. Auth and Security

- [x] Local JWT mode remains canonical default.
- [x] Sync JWT verification in async flows runs on thread boundary.
- [x] Remote auth mode is optional and fail-closed.
- [x] RFC6750 `WWW-Authenticate` behavior verified.
- [x] Logging sanitization blocks token/presigned URL leakage.

## 3. Async and Reliability

- [x] Enqueue failures return `503` with `queue_unavailable`.
- [x] Failed enqueue responses are not replay-cached as success.
- [x] Worker result-update transition guardrails enforced.
- [x] `status=succeeded` worker updates always clear `error` state.
- [x] Queue lag + worker throughput metrics emitted.
- [x] SQS publisher retry configuration and error mappings validated.

## 4. Cache and Readiness

- [x] Two-tier cache behavior (local + shared) validated.
- [x] Redis outage fallback behavior validated.
- [x] Cache hit/miss/fallback counters validated.
- [x] `/v1/health/ready` excludes feature-flag pass/fail coupling.
- [x] Missing/blank `FILE_TRANSFER_BUCKET` fails readiness.

## 5. Cross-Repo Compatibility

- [x] Nova release docs and CI/CD template mappings are aligned to `infra/nova/**`.
- [x] `JOBS_SQS_RETRY_MODE` and
  `JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS` contract aligned.
- [x] `dash-pca` migration to `nova_dash_bridge` and canonical routes complete.
- [x] `dash-pca` async uploader and settings aliases validated.

## 6. Final Live Gates (External AWS Execution Required)

- [x] Operator runbook is published:
  `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- Note: runbook publication is complete; the live gates below remain blocked
  pending non-prod AWS access and must be completed during staged rollout.
- [x] Gate preflight evidence recorded with current blockers:
  `docs/plan/release/evidence-log.md` (entry `2026-03-03T08:29:33Z`).
- [x] Gate rerun evidence recorded under `bjorn-dev`:
  `docs/plan/release/evidence-log.md` (entry `2026-03-03T09:32:00Z`).
- Note: remaining blocker is CI/CD stack update authority
  (`iam:PassRole` denied for `nova-ci-nova-codepipeline-role`) plus missing
  deployed runtime inventory for ECS-native blue/green live gates.
- [ ] Sidecar ALB route + health behavior validated in non-prod AWS.
- [ ] Non-prod end-to-end smoke completed.
- [ ] CloudWatch dashboards/alarms synthetic-failure validation completed.

## 7. Release Artifacts

- [x] Final release notes published:
  `docs/history/2026-02-cutover/release/RELEASE-NOTES-2026-02-12.md`

## 8. Target-State Capability Checklist (Implemented)

- [x] `/v1/jobs` capability surface implemented and documented.
- [x] `/v1/jobs/{id}/events` event contract implemented and documented.
- [x] `/v1/capabilities`, `/v1/resources/plan`, `/v1/releases/info` delivered.
- [x] `/v1/health/live` and `/v1/health/ready` implemented with
  the current aggregate readiness semantics.
- [x] `SPEC-0015` workflow artifacts from `.github/workflows/` are present and
  validated in this release path:
  `publish-packages.yml`, `deploy-dev.yml`, `promote-prod.yml`,
  `post-deploy-validate.yml`, `conformance-clients.yml`.
